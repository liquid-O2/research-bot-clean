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
from .campaign import RawPrefixFidelityEvidence, TeacherAlignmentEvidence
from .context_sources import (
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
    CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS, EVENT_DTYPE, EventPack,
)
from .plan_contract import (
    CLOCK_LAW_RECEIPT_FILE_SHA256,
    CLOCK_LAW_RECEIPT_RELATIVE,
    CLOCK_LAW_SHA256,
)
from .policy import ModelInputBinding
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
from .selected_horizon_contract import (
    COVERAGE_LAW as SELECTED_HORIZON_COVERAGE_LAW,
    COVERAGE_LAW_SHA256 as SELECTED_HORIZON_COVERAGE_LAW_SHA256,
    COVERAGE_SCHEMA as SELECTED_HORIZON_COVERAGE_SCHEMA,
    SelectedHorizonContractRefusal,
    selected_horizon_coverage_receipt,
    validate_selected_horizon_coverage,
)
from .teacher import TeacherPath, TeacherStore, build_teacher_store
from .train import (
    EntrySessionSpec,
    HORIZONS_SECONDS,
    ReplayCalibrationData,
    SelfSupervisedTargets,
    _static_context_summary,
)


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
FORECAST_SCHEMA = "QRE2FORECAST4"
EXPLICIT_FORECAST_SCHEMA = "entry-v2-explicit-forecast-test-adapter-v1"
QRE2_FORECAST_LAW_SHA256 = (
    "6b43efa63272f370aa7fc3331446ff30cd616acf12e897aef13062fdf19b3a3b"
)


@runtime_checkable
class DiagnosticSessionObserver(Protocol):
    """Consumes one verified session while its sole full mmap is open.

    Implementations must materialize only compact owned truth and must not
    retain ``pack`` or any view sharing its storage.  The learner prefix is
    published to ``source.array_cache`` before this callback runs.
    """

    def observe_session(
        self,
        *,
        source: SessionEventSource,
        pack: EventPack,
        candidates: tuple[Mapping[str, str], ...],
        teachers: tuple[Mapping[str, str], ...],
    ) -> None: ...

    def observe_cached_session(
        self, *, source: SessionEventSource,
        candidates: tuple[Mapping[str, str], ...],
        teachers: tuple[Mapping[str, str], ...],
    ) -> None: ...
SENTINEL_HIGH = 1 << 62
RAW_PRICE_SCALE = 1.0e-9
ASSET_MULTIPLIER = MappingProxyType({"SI": 5_000, "HG": 25_000, "NKD": 5})
ASSET_RAW_TICK = MappingProxyType({
    "SI": 5_000_000,
    "HG": 500_000,
    "NKD": 5_000_000_000,
})


def _verified_session_identity(
    asset: str, d8: int, candidate_manifest_row: Mapping[str, str],
    teacher_manifest_row: Mapping[str, str],
) -> Mapping[str, Any]:
    C.guard_date(int(d8))
    return MappingProxyType({
        "schema": "entry-v2-verified-session-source-v1",
        "asset": asset,
        "d8": int(d8),
        "candidate_manifest_row": dict(candidate_manifest_row),
        "teacher_manifest_row": dict(teacher_manifest_row),
        "corpus_schema": CORPUS_SCHEMA,
        "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
        "clock_law_receipt_sha256": CLOCK_LAW_RECEIPT_FILE_SHA256,
    })


class _VerifiedPackView:
    """Immutable prefix-only view restored from a verified-session product."""

    def __init__(self, path: Path, rows: np.ndarray,
                 source_pin: Mapping[str, Any], event_hash: str) -> None:
        self.path = path
        self.rows = rows
        self.header = SimpleNamespace(
            asset=str(source_pin["asset"]), d8=int(source_pin["d8"]),
            locked_iid=int(source_pin["locked_iid"]),
            open_utc=int(source_pin["open_utc"]),
            close_utc=int(source_pin["close_utc"]),
            n_events=int(source_pin["event_count"]),
        )
        self.sidecar = MappingProxyType({
            "schema": "QRE2EVENTMETA2", "event_pack_sha256": event_hash,
            "record_window": {
                "start_d8": int(source_pin["record_start_d8"]),
                "end_d8_exclusive": int(source_pin["record_end_d8_exclusive"]),
            },
        })

    def cutoff(self, decision_ts_ns: int) -> int:
        return int(np.searchsorted(
            self.rows["ts_recv_ns"], np.uint64(decision_ts_ns), side="left"
        ))

    def close(self) -> None:
        return None

FORECAST_QUANTILES = ("q10", "q25", "q50", "q75", "q90")
FORECAST_SEGMENTS = ("SESSION", "TOKYO", "LONDON", "NY")
PHASE_FORECAST_SEGMENT = MappingProxyType({0: "TOKYO", 1: "LONDON", 2: "NY"})
FORECAST_SCOPE_FIELDS = (
    "forecast_age_sec", "sigma_hat_usd", "range_hat_usd",
    "sigma_components_present", "sigma_raw_hat_usd",
    "sigma_persistence_usd", "sigma_calibration_ratio",
    "sigma_calibration_count", "sigma_calibrated_hat_usd",
    "sigma_shrinkage_delta_usd", "sigma_ols_minus_persistence_usd",
    "sigma_ols_over_persistence",
    *(f"move_{quantile}_usd" for quantile in FORECAST_QUANTILES),
    "rv5_over_rv66", "rv5_over_rv66_present",
    "regime_low_present", "regime_mid_present", "regime_high_present",
    "regime_present", "move_ladder_present",
    "unscaled_fallback_present", "forecast_present",
    "vintage_history_present", "vintage_ready_count_5",
    "vintage_ready_count_22",
    "vintage_sigma_delta_1_usd", "vintage_sigma_slope_5_usd",
    "vintage_sigma_slope_22_usd", "vintage_sigma_acceleration_usd",
    "vintage_range_delta_1_usd", "vintage_range_slope_5_usd",
    "vintage_range_slope_22_usd", "vintage_range_acceleration_usd",
    "vintage_q50_delta_1_usd", "vintage_q50_slope_5_usd",
    "vintage_q50_slope_22_usd", "vintage_q50_acceleration_usd",
    "vintage_q90_delta_1_usd", "vintage_q90_slope_5_usd",
    "vintage_q90_slope_22_usd", "vintage_q90_acceleration_usd",
    "vintage_rv_ratio_delta_1", "vintage_rv_ratio_slope_5",
    "vintage_rv_ratio_slope_22", "vintage_rv_ratio_acceleration",
    "vintage_regime_changed", "vintage_regime_persistence",
)
FORECAST_FEATURE_FIELDS = tuple(
    f"{scope}_{name}"
    for scope in ("session", "phase")
    for name in FORECAST_SCOPE_FIELDS
)

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

_FORECAST_COLUMNS = (
    "asset", "d8", "segment", "status", "missing_reason",
    "history_end_d8", "availability_ts_ns", "fit_month",
    "fit_end_range_d8", "fit_end_sigma_d8", "n_train_range", "rank_range",
    "n_train_sigma", "rank_sigma", "rv1_usd", "rv5_usd", "rv22_usd",
    "prior_parkinson_usd", "prior_gk_usd", "prior_rs_usd", "prior_jump_usd",
    "sigma_raw_hat_usd", "sigma_persistence_usd",
    "sigma_calibration_ratio", "n_sigma_calibration", "sigma_hat_usd",
    "range_hat_usd", "rv5_over_rv66", "regime_cut_lo",
    "regime_cut_hi", "regime_tag", "ladder_source", "n_calibration",
    "n_regime_calibration",
    *(name for quantile in FORECAST_QUANTILES
      for name in (f"move_{quantile}_ratio", f"move_{quantile}_usd")),
    *(name for quantile in FORECAST_QUANTILES
      for name in (f"move_rs_{quantile}_ratio", f"move_rs_{quantile}_usd")),
    "phase_profile_sha256", "model_sha256", "history_source_sha256",
    "lineage_sha256",
)

_SHA = re.compile(r"[0-9a-f]{64}")
_CANDIDATE_MANIFEST_COLUMNS = (
    "asset", "d8", "status", "rows", "raw_events", "two_sided_events",
    "sane_events", "candidate_file", "candidate_sha256", "event_pack_sha256",
    "receipt_file", "receipt_sha256",
)
_TEACHER_MANIFEST_COLUMNS = (
    "asset", "d8", "rows", "ready", "refused", "teacher_file",
    "teacher_sha256", "candidate_sha256", "event_pack_sha256",
    "receipt_file", "receipt_sha256",
)
_LOCK_COLUMNS = (
    "asset", "d8", "status", "locked_iid", "selection_basis_d8",
    "selection_basis_updates", "selection_basis_symbol", "open_utc",
    "close_utc",
)
_CANDIDATE_COLUMNS = (
    "candidate_id", "asset", "d8", "locked_iid", "selection_basis_d8",
    "confirmation_ts_recv_ns", "confirmation_event_ordinal", "decision_ts_ns",
    "decision_sec", "side", "phase", "rung_mask", "delay", "phase_open_utc",
    "phase_close_utc", "event_cutoff", "prefix_last_event_ordinal",
    "prefix_last_availability_ts_ns", "event_pack_sha256", "prefix_sha256",
    "clock_law_receipt_sha256", "lineage_sha256", "entry_bid_px", "entry_ask_px",
    "entry_mid2", "entry_spread_usd", "frozen_cost_usd",
    "atr14_prev_usd", "spread_prior_present", "spread_prior_usd",
    "sane_ceiling_usd", "compliance_status", "compliance_distance_sec",
    "compliance_artifact_sha256",
)
_TEACHER_COLUMNS = (
    "candidate_id", "asset", "d8", "decision_ts_ns", "exit_ts_ns",
    "phase_close_utc", "status", "cert_close_usd", "mfe_usd", "mae_usd",
    "time_to_peak_sec", "wall_hit", "payer", "take_target",
    "compliance_status",
)


def _sha(value: object, name: str) -> str:
    text = str(value)
    if _SHA.fullmatch(text) is None:
        raise C.EntryV2Refusal(f"invalid {name} sha256")
    return text


def _embedded_receipt(value: Mapping[str, Any], name: str) -> str:
    payload = dict(value)
    claimed = _sha(payload.pop("receipt_sha256", ""), name)
    if C.object_sha256(payload) != claimed:
        raise C.EntryV2Refusal(f"{name} content hash mismatch")
    return claimed


def _guard_path_before_open(path: Path) -> None:
    # Apply the wall to every component before is_file/stat/open/resolve follows.
    for component in path.parts:
        for d8 in C.dates_in_basename(component):
            C.guard_date(d8)


def _read_pinned(path: Path, expected_sha256: str, name: str) -> bytes:
    _guard_path_before_open(path)
    expected = _sha(expected_sha256, name)
    if not path.is_file():
        raise C.EntryV2Refusal(f"missing {name}: {path}")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise C.EntryV2Refusal(
            f"{name} hash mismatch: expected={expected} actual={actual}"
        )
    return raw


def _under(root: Path, relative: str, d8: int) -> Path:
    C.guard_date(int(d8))  # must precede resolving or opening the referenced path
    raw = Path(relative)
    _guard_path_before_open(raw)
    if raw.is_absolute():
        raise C.EntryV2Refusal("artifact manifest contains an absolute path")
    resolved_root = root.resolve()
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise C.EntryV2Refusal("artifact manifest path escapes output root") from exc
    return resolved


def _table(raw: bytes, schema: str, columns: Sequence[str], name: str,
           *, d8: int | None = None) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise C.EntryV2Refusal(f"{name} is not UTF-8") from exc
    lines = text.splitlines()
    suffix = r" d8=(\d{8})" if d8 is not None else ""
    header = re.fullmatch(
        rf"# {re.escape(schema)} start_d8=(\d{{8}}) "
        rf"end_d8_exclusive=(\d{{8}}){suffix}",
        lines[0] if lines else "")
    if len(lines) < 2 or header is None:
        raise C.EntryV2Refusal(f"{name} schema mismatch")
    start_d8, end_d8 = int(header.group(1)), int(header.group(2))
    C.guard_decode_window(start_d8, end_d8)
    if d8 is not None:
        header_d8 = int(header.group(3))
        if header_d8 != int(d8) or not start_d8 <= header_d8 < end_d8:
            raise C.EntryV2Refusal(f"{name} header date/window mismatch")
    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])), delimiter="\t")
    if tuple(reader.fieldnames or ()) != tuple(columns):
        raise C.EntryV2Refusal(f"{name} column schema mismatch")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise C.EntryV2Refusal(f"{name} row width mismatch")
    return rows


def _int(row: Mapping[str, str], name: str) -> int:
    try:
        return int(row[name])
    except (KeyError, ValueError) as exc:
        raise C.EntryV2Refusal(f"invalid integer field {name}") from exc


def _float(row: Mapping[str, str], name: str, *, optional: bool = False,
           ) -> float | None:
    value = row.get(name, "")
    if optional and value == "NA":
        return None
    try:
        out = float(value)
    except ValueError as exc:
        raise C.EntryV2Refusal(f"invalid float field {name}") from exc
    if not math.isfinite(out):
        raise C.EntryV2Refusal(f"non-finite float field {name}")
    return out


def _bit(row: Mapping[str, str], name: str) -> bool:
    value = _int(row, name)
    if value not in (0, 1):
        raise C.EntryV2Refusal(f"invalid boolean field {name}")
    return bool(value)


def _json_receipt(raw: bytes, *, schema: str, stage: str, asset: str,
                  manifest_sha256: str, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid {name} JSON") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal(f"invalid {name} object")
    if (value.get("schema"), value.get("stage"), value.get("asset")) != (
            schema, stage, asset):
        raise C.EntryV2Refusal(f"{name} identity mismatch")
    if value.get("manifest_sha256") != manifest_sha256:
        raise C.EntryV2Refusal(f"{name} manifest pin mismatch")
    try:
        start = int(value["start_d8"])
        end = int(value["end_d8_exclusive"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal(f"{name} has an invalid record window") from exc
    C.guard_decode_window(start, end)
    if value.get("holdout_start_d8") != C.HOLDOUT_START_D8:
        raise C.EntryV2Refusal(f"{name} holdout wall mismatch")
    if value.get("final_exam_permit") is not False:
        raise C.EntryV2Refusal(f"{name} is not an ordinary development artifact")
    return value


@dataclass(frozen=True, slots=True)
class AssetArtifactSet:
    """Externally pinned artifact roots printed by the C++ G1 driver."""

    root: Path
    asset: str
    candidate_manifest_sha256: str
    teacher_manifest_sha256: str
    candidate_receipt_sha256: str
    teacher_receipt_sha256: str

    def __post_init__(self) -> None:
        root = Path(self.root)
        _guard_path_before_open(root)
        object.__setattr__(self, "root", root)
        asset = str(self.asset).upper()
        if asset not in C.ASSETS:
            raise C.EntryV2Refusal(f"unsupported artifact asset: {asset}")
        object.__setattr__(self, "asset", asset)
        for name in (
            "candidate_manifest_sha256", "teacher_manifest_sha256",
            "candidate_receipt_sha256", "teacher_receipt_sha256",
        ):
            _sha(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class ForecastQuery:
    candidate_id: str
    asset: str
    trading_day: int
    decision_ts_ns: int
    phase: int


@dataclass(frozen=True, slots=True)
class ForecastSegmentSnapshot:
    """One pinned QRE2FORECAST4 segment reduced to student-visible fields."""

    segment: str
    status: str
    availability_ts_ns: int
    sigma_hat_usd: float | None
    range_hat_usd: float | None
    move_usd: tuple[float | None, ...]
    rv5_over_rv66: float | None
    regime: str
    ladder_source: str
    lineage_sha256: str
    sigma_raw_hat_usd: float | None = None
    sigma_persistence_usd: float | None = None
    sigma_calibration_ratio: float | None = None
    n_sigma_calibration: int | None = None

    def validate(self, *, expected_segment: str, decision_ts_ns: int) -> None:
        if self.segment != expected_segment or self.segment not in FORECAST_SEGMENTS:
            raise C.EntryV2Refusal("forecast segment/candidate phase mismatch")
        if not 0 < int(self.availability_ts_ns) < int(decision_ts_ns):
            raise C.EntryV2Refusal("forecast availability is not strictly prior")
        if len(self.move_usd) != len(FORECAST_QUANTILES):
            raise C.EntryV2Refusal("forecast move ladder width mismatch")
        _sha(self.lineage_sha256, "forecast row lineage")
        if self.status == "MISSING":
            if (self.sigma_hat_usd is not None or self.range_hat_usd is not None
                    or self.sigma_raw_hat_usd is not None
                    or self.sigma_persistence_usd is not None
                    or self.sigma_calibration_ratio is not None
                    or self.n_sigma_calibration is not None
                    or self.rv5_over_rv66 is not None
                    or any(value is not None for value in self.move_usd)
                    or self.regime != "NA" or self.ladder_source != "MISSING"):
                raise C.EntryV2Refusal("MISSING forecast segment carries student values")
            return
        if self.status != "READY":
            raise C.EntryV2Refusal("forecast segment has an unknown status")
        if self.ladder_source not in {
                "MISSING", "REGIME", "UNSCALED_FALLBACK"}:
            raise C.EntryV2Refusal("READY forecast segment has an invalid ladder source")
        if self.regime not in {"NA", "LOW", "MID", "HIGH"}:
            raise C.EntryV2Refusal("READY forecast segment has an invalid regime")
        required = (self.sigma_hat_usd, self.range_hat_usd)
        if (any(value is None or not math.isfinite(float(value)) for value in required)
                or float(self.sigma_hat_usd) <= 0.0
                or float(self.range_hat_usd) <= 0.0):
            raise C.EntryV2Refusal("READY forecast segment has invalid numeric values")
        components = (self.sigma_raw_hat_usd, self.sigma_persistence_usd,
                      self.sigma_calibration_ratio)
        if any(value is not None for value in components):
            if (any(value is None or not math.isfinite(float(value))
                    or float(value) <= 0.0 for value in components)
                    or self.n_sigma_calibration is None
                    or not 0 <= int(self.n_sigma_calibration) <= 66):
                raise C.EntryV2Refusal("forecast sigma components are invalid")
        if self.ladder_source == "MISSING":
            if any(value is not None for value in self.move_usd):
                raise C.EntryV2Refusal("missing forecast ladder carries move values")
        elif any(value is None or not math.isfinite(float(value))
                 for value in self.move_usd):
            raise C.EntryV2Refusal("present forecast ladder has invalid move values")
        if self.rv5_over_rv66 is not None and not math.isfinite(
                float(self.rv5_over_rv66)):
            raise C.EntryV2Refusal("forecast regime ratio is non-finite")


@dataclass(frozen=True, slots=True)
class ForecastRow:
    """Candidate join of exact SESSION and candidate-phase forecast rows."""

    candidate_id: str
    asset: str
    trading_day: int
    decision_ts_ns: int
    phase: int
    session: ForecastSegmentSnapshot
    phase_segment: ForecastSegmentSnapshot
    source_sha256: str

    def validate(self, query: ForecastQuery) -> None:
        if (self.candidate_id, self.asset, int(self.trading_day),
                int(self.decision_ts_ns), int(self.phase)) != (
                query.candidate_id, query.asset, query.trading_day,
                query.decision_ts_ns, query.phase):
            raise C.EntryV2Refusal("forecast row/candidate identity mismatch")
        C.guard_date(int(self.trading_day))
        if self.phase not in PHASE_FORECAST_SEGMENT:
            raise C.EntryV2Refusal("forecast query has an invalid candidate phase")
        self.session.validate(expected_segment="SESSION",
                              decision_ts_ns=self.decision_ts_ns)
        self.phase_segment.validate(
            expected_segment=PHASE_FORECAST_SEGMENT[self.phase],
            decision_ts_ns=self.decision_ts_ns)
        _sha(self.source_sha256, "forecast source")


@runtime_checkable
class ForecastProvider(Protocol):
    receipt_sha256: str
    assets: frozenset[str]

    def forecast(self, query: ForecastQuery) -> ForecastRow | None: ...

    def session_regime(
        self, asset: str, trading_day: int
    ) -> ForecastSegmentSnapshot | None: ...

    def forecast_history(
        self, asset: str, trading_day: int, segment: str,
        decision_ts_ns: int, limit: int,
    ) -> tuple[ForecastSegmentSnapshot, ...]: ...


@dataclass(frozen=True, slots=True)
class AssetScopedForecastProvider:
    """One-asset view that preserves the full provider receipt identity.

    The production corpus is built in independent asset lanes.  Forecast row
    lineage includes the provider receipt, so constructing three smaller
    providers would silently change every example.  This view narrows only the
    allowed query surface while delegating to the already-verified immutable
    all-asset provider.
    """

    delegate: ForecastProvider
    asset: str

    def __post_init__(self) -> None:
        if not isinstance(self.delegate, ForecastProvider):
            raise C.EntryV2Refusal("asset-scoped forecast delegate is invalid")
        asset = str(self.asset).upper()
        if asset not in C.ASSETS or asset not in self.delegate.assets:
            raise C.EntryV2Refusal("asset-scoped forecast asset is unavailable")
        object.__setattr__(self, "asset", asset)
        _sha(self.delegate.receipt_sha256, "forecast receipt")

    @property
    def receipt_sha256(self) -> str:
        return self.delegate.receipt_sha256

    @property
    def assets(self) -> frozenset[str]:
        return frozenset((self.asset,))

    def forecast(self, query: ForecastQuery) -> ForecastRow | None:
        if query.asset != self.asset:
            raise C.EntryV2Refusal("forecast query escaped its asset lane")
        return self.delegate.forecast(query)

    def session_regime(
        self, asset: str, trading_day: int
    ) -> ForecastSegmentSnapshot | None:
        if str(asset).upper() != self.asset:
            raise C.EntryV2Refusal("forecast regime query escaped its asset lane")
        return self.delegate.session_regime(asset, trading_day)

    def forecast_history(
        self, asset: str, trading_day: int, segment: str,
        decision_ts_ns: int, limit: int,
    ) -> tuple[ForecastSegmentSnapshot, ...]:
        if str(asset).upper() != self.asset:
            raise C.EntryV2Refusal("forecast history query escaped its asset lane")
        return self.delegate.forecast_history(
            asset, trading_day, segment, decision_ts_ns, limit)


def _is_test_forecast_provider(provider: ForecastProvider) -> bool:
    if isinstance(provider, ExplicitForecastRows):
        return True
    if isinstance(provider, AssetScopedForecastProvider):
        return _is_test_forecast_provider(provider.delegate)
    return False


@dataclass(frozen=True, slots=True)
class ExplicitForecastRows:
    """Hash-pinned test adapter; production uses QRE2ForecastProvider."""

    rows: tuple[ForecastRow, ...]
    receipt_sha256: str = ""

    def __post_init__(self) -> None:
        by_id: dict[str, ForecastRow] = {}
        for row in self.rows:
            if not row.candidate_id or row.candidate_id in by_id:
                raise C.EntryV2Refusal("duplicate/empty explicit forecast candidate_id")
            by_id[row.candidate_id] = row
        payload = {
            "schema": EXPLICIT_FORECAST_SCHEMA,
            "feature_fields": list(FORECAST_FEATURE_FIELDS),
            "rows": [
                {
                    "candidate_id": row.candidate_id,
                    "asset": row.asset,
                    "trading_day": row.trading_day,
                    "decision_ts_ns": row.decision_ts_ns,
                    "phase": row.phase,
                    "session": _forecast_snapshot_payload(row.session),
                    "phase_segment": _forecast_snapshot_payload(row.phase_segment),
                    "source_sha256": row.source_sha256,
                }
                for row in sorted(self.rows, key=lambda item: item.candidate_id)
            ],
        }
        computed = C.object_sha256(payload)
        if self.receipt_sha256 and self.receipt_sha256 != computed:
            raise C.EntryV2Refusal("explicit forecast receipt mismatch")
        object.__setattr__(self, "receipt_sha256", computed)

    def forecast(self, query: ForecastQuery) -> ForecastRow | None:
        return next((row for row in self.rows
                     if row.candidate_id == query.candidate_id), None)

    def session_regime(
        self, asset: str, trading_day: int
    ) -> ForecastSegmentSnapshot | None:
        rows = {
            row.session
            for row in self.rows
            if row.asset == asset and row.trading_day == int(trading_day)
        }
        if len(rows) > 1:
            raise C.EntryV2Refusal(
                "explicit forecasts disagree on the asset-day session regime"
            )
        return next(iter(rows), None)

    def forecast_history(
        self, asset: str, trading_day: int, segment: str,
        decision_ts_ns: int, limit: int,
    ) -> tuple[ForecastSegmentSnapshot, ...]:
        if segment not in FORECAST_SEGMENTS or limit < 1:
            raise C.EntryV2Refusal("explicit forecast history query is invalid")
        by_day: dict[int, ForecastSegmentSnapshot] = {}
        for row in self.rows:
            if row.asset != asset or int(row.trading_day) >= int(trading_day):
                continue
            snapshot = (row.session if segment == "SESSION" else
                        row.phase_segment if row.phase_segment.segment == segment
                        else None)
            if (snapshot is not None
                    and int(snapshot.availability_ts_ns) < int(decision_ts_ns)):
                prior = by_day.get(int(row.trading_day))
                if prior is not None and prior != snapshot:
                    raise C.EntryV2Refusal(
                        "explicit forecast history disagrees within an asset-day")
                by_day[int(row.trading_day)] = snapshot
        return tuple(by_day[day] for day in sorted(by_day)[-int(limit):])

    @property
    def assets(self) -> frozenset[str]:
        return frozenset(row.asset for row in self.rows)


@dataclass(frozen=True, slots=True)
class QRE2ForecastArtifactInput:
    root: Path
    asset: str
    artifact_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        root = Path(self.root)
        _guard_path_before_open(root)
        object.__setattr__(self, "root", root)
        asset = str(self.asset).upper()
        if asset not in C.ASSETS:
            raise C.EntryV2Refusal("unsupported QRE2 forecast asset")
        object.__setattr__(self, "asset", asset)
        _sha(self.artifact_sha256, "forecast artifact")
        _sha(self.receipt_sha256, "forecast receipt")


class QRE2ForecastProvider:
    """Verified production reader for C++ QRE2FORECAST4 artifacts."""

    def __init__(self, inputs: Sequence[QRE2ForecastArtifactInput]) -> None:
        if not inputs:
            raise C.EntryV2Refusal("QRE2 forecast artifacts cannot be empty")
        assets = [item.asset for item in inputs]
        if len(assets) != len(set(assets)):
            raise C.EntryV2Refusal("duplicate QRE2 forecast artifact asset")
        rows: dict[tuple[str, int, str], ForecastSegmentSnapshot] = {}
        pins: list[dict[str, str]] = []
        for item in sorted(inputs, key=lambda value: value.asset):
            parsed, law_sha = _read_qre2_forecast(item)
            for key, value in parsed.items():
                if key in rows:
                    raise C.EntryV2Refusal("duplicate QRE2 forecast row key")
                rows[key] = value
            pins.append({
                "asset": item.asset,
                "artifact_sha256": item.artifact_sha256,
                "receipt_sha256": item.receipt_sha256,
                "law_sha256": law_sha,
            })
        self._rows = MappingProxyType(rows)
        history: dict[tuple[str, str], tuple[
                tuple[int, ForecastSegmentSnapshot], ...]] = {}
        for asset in assets:
            for segment in FORECAST_SEGMENTS:
                history[(asset, segment)] = tuple(sorted(
                    ((day, snapshot)
                     for (row_asset, day, row_segment), snapshot in rows.items()
                     if row_asset == asset and row_segment == segment),
                    key=lambda item: item[0]))
        self._history = MappingProxyType(history)
        self._artifacts = MappingProxyType({item.asset: item.artifact_sha256
                                            for item in inputs})
        self.assets = frozenset(assets)
        self.receipt_sha256 = C.object_sha256({
            "schema": "entry-v2-qre2-forecast-provider-v4", "artifacts": pins})

    def forecast(self, query: ForecastQuery) -> ForecastRow | None:
        phase_name = PHASE_FORECAST_SEGMENT.get(int(query.phase))
        if phase_name is None:
            raise C.EntryV2Refusal("forecast query has an invalid phase")
        session = self._rows.get((query.asset, query.trading_day, "SESSION"))
        phase = self._rows.get((query.asset, query.trading_day, phase_name))
        if session is None or phase is None:
            return None
        artifact_sha = self._artifacts.get(query.asset)
        if artifact_sha is None:
            return None
        return ForecastRow(
            query.candidate_id, query.asset, query.trading_day,
            query.decision_ts_ns, query.phase, session, phase, artifact_sha)

    def session_regime(
        self, asset: str, trading_day: int
    ) -> ForecastSegmentSnapshot | None:
        return self._rows.get((str(asset).upper(), int(trading_day), "SESSION"))

    def forecast_history(
        self, asset: str, trading_day: int, segment: str,
        decision_ts_ns: int, limit: int,
    ) -> tuple[ForecastSegmentSnapshot, ...]:
        asset = str(asset).upper()
        if (asset not in self.assets or segment not in FORECAST_SEGMENTS
                or int(limit) < 1):
            raise C.EntryV2Refusal("QRE2 forecast history query is invalid")
        selected = [snapshot for day, snapshot in self._history[(asset, segment)]
                    if (int(day) < int(trading_day)
                        and int(snapshot.availability_ts_ns)
                        < int(decision_ts_ns))]
        return tuple(selected[-int(limit):])


def _forecast_snapshot_payload(row: ForecastSegmentSnapshot) -> dict[str, Any]:
    return {
        "segment": row.segment,
        "status": row.status,
        "availability_ts_ns": row.availability_ts_ns,
        "sigma_hat_usd": row.sigma_hat_usd,
        "sigma_raw_hat_usd": row.sigma_raw_hat_usd,
        "sigma_persistence_usd": row.sigma_persistence_usd,
        "sigma_calibration_ratio": row.sigma_calibration_ratio,
        "n_sigma_calibration": row.n_sigma_calibration,
        "range_hat_usd": row.range_hat_usd,
        "move_usd": list(row.move_usd),
        "rv5_over_rv66": row.rv5_over_rv66,
        "regime": row.regime,
        "ladder_source": row.ladder_source,
        "lineage_sha256": row.lineage_sha256,
    }


def _forecast_optional(row: Mapping[str, str], name: str) -> float | None:
    return _float(row, name, optional=True)


def _forecast_lineage(row: Mapping[str, str], law_sha256: str) -> str:
    segment_index = {name: index for index, name in enumerate(FORECAST_SEGMENTS)}
    status_index = {"READY": 0, "MISSING": 1}
    reason_index = {
        "NONE": 0, "DESIGN_HISTORY": 1, "MIN_TRAIN": 2,
        "RANK_DEFICIENT": 3, "NONFINITE_PREDICTION": 4,
    }
    regime_index = {"NA": 0, "LOW": 1, "MID": 2, "HIGH": 3}
    ladder_index = {"MISSING": 0, "REGIME": 1, "UNSCALED_FALLBACK": 2}
    try:
        enums = (
            segment_index[row["segment"]], status_index[row["status"]],
            reason_index[row["missing_reason"]], regime_index[row["regime_tag"]],
            ladder_index[row["ladder_source"]],
        )
    except KeyError as exc:
        raise C.EntryV2Refusal("unknown QRE2 forecast enum") from exc
    asset_index = C.ASSET_INDEX.get(row.get("asset", ""))
    if asset_index is None:
        raise C.EntryV2Refusal("unknown QRE2 forecast asset")

    int_fields = (
        "d8", "history_end_d8", "availability_ts_ns", "fit_month",
        "fit_end_range_d8", "fit_end_sigma_d8", "n_train_range", "rank_range",
        "n_train_sigma", "rank_sigma", "n_sigma_calibration",
        "n_calibration", "n_regime_calibration",
    )
    for name in int_fields:
        value = _int(row, name)
        if row[name] != str(value):
            raise C.EntryV2Refusal(f"non-canonical QRE2 forecast integer: {name}")
    pre_sigma_float_fields = (
        "rv1_usd", "rv5_usd", "rv22_usd", "prior_parkinson_usd",
        "prior_gk_usd", "prior_rs_usd", "prior_jump_usd",
        "sigma_raw_hat_usd", "sigma_persistence_usd",
        "sigma_calibration_ratio",
    )
    post_sigma_float_fields = (
        "sigma_hat_usd", "range_hat_usd", "rv5_over_rv66",
        "regime_cut_lo", "regime_cut_hi",
    )
    move_ratio_fields = tuple(f"move_{q}_ratio" for q in FORECAST_QUANTILES)
    move_usd_fields = tuple(f"move_{q}_usd" for q in FORECAST_QUANTILES)
    regime_ratio_fields = tuple(f"move_rs_{q}_ratio" for q in FORECAST_QUANTILES)
    regime_usd_fields = tuple(f"move_rs_{q}_usd" for q in FORECAST_QUANTILES)
    float_fields = (pre_sigma_float_fields + post_sigma_float_fields
                    + move_ratio_fields + move_usd_fields
                    + regime_ratio_fields + regime_usd_fields)
    for name in float_fields:
        _forecast_optional(row, name)
    cpp = lambda name: "nan" if row[name] == "NA" else row[name]
    parts = [
        "QRE2FORECASTROW4", law_sha256, str(asset_index), row["d8"],
        str(enums[0]), str(enums[1]), str(enums[2]), row["history_end_d8"],
        row["availability_ts_ns"], row["fit_month"], row["fit_end_range_d8"],
        row["fit_end_sigma_d8"], row["n_train_range"], row["rank_range"],
        row["n_train_sigma"], row["rank_sigma"],
        *(cpp(name) for name in pre_sigma_float_fields),
        row["n_sigma_calibration"],
        *(cpp(name) for name in post_sigma_float_fields),
        str(enums[3]), str(enums[4]), row["n_calibration"],
        row["n_regime_calibration"],
        *(cpp(name) for name in move_ratio_fields),
        *(cpp(name) for name in move_usd_fields),
        *(cpp(name) for name in regime_ratio_fields),
        *(cpp(name) for name in regime_usd_fields),
        row["phase_profile_sha256"], row["model_sha256"],
        row["history_source_sha256"],
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _read_qre2_forecast(
    item: QRE2ForecastArtifactInput,
) -> tuple[dict[tuple[str, int, str], ForecastSegmentSnapshot], str]:
    artifact_path = item.root / "forecast" / f"{item.asset}.qrf4.tsv"
    receipt_path = item.root / "forecast" / f"{item.asset}.qrf4.json"
    artifact_raw = _read_pinned(
        artifact_path, item.artifact_sha256, f"{item.asset} QRE2 forecast artifact")
    receipt_raw = _read_pinned(
        receipt_path, item.receipt_sha256, f"{item.asset} QRE2 forecast receipt")
    try:
        text = artifact_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise C.EntryV2Refusal("QRE2 forecast artifact is not UTF-8") from exc
    lines = text.splitlines()
    header = re.fullmatch(
        r"# QRE2FORECAST4 start_d8=(\d{8}) end_d8_exclusive=(\d{8}) "
        r"asset=(SI|HG|NKD) law_sha256=([0-9a-f]{64})",
        lines[0] if lines else "")
    if len(lines) < 2 or header is None or header.group(3) != item.asset:
        raise C.EntryV2Refusal("QRE2 forecast header mismatch")
    start_d8, end_d8 = int(header.group(1)), int(header.group(2))
    law_sha = _sha(header.group(4), "forecast law")
    if law_sha != QRE2_FORECAST_LAW_SHA256:
        raise C.EntryV2Refusal("QRE2 forecast model-law hash mismatch")
    C.guard_decode_window(start_d8, end_d8)
    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])), delimiter="\t")
    if tuple(reader.fieldnames or ()) != _FORECAST_COLUMNS:
        raise C.EntryV2Refusal("QRE2 forecast column schema mismatch")
    raw_rows = list(reader)
    if any(None in row or any(value is None for value in row.values())
           for row in raw_rows):
        raise C.EntryV2Refusal("QRE2 forecast row width mismatch")

    try:
        receipt = json.loads(receipt_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("invalid QRE2 forecast receipt JSON") from exc
    if not isinstance(receipt, dict) or (
            receipt.get("schema"), receipt.get("asset"),
            receipt.get("forecast_law_sha256"), receipt.get("output_sha256"),
            receipt.get("holdout_start_d8"), receipt.get("final_exam_permit")) != (
                "QRE2FORECASTRECEIPT4", item.asset, law_sha,
                item.artifact_sha256, C.HOLDOUT_START_D8, False):
        raise C.EntryV2Refusal("QRE2 forecast receipt identity/hash mismatch")
    try:
        receipt_start = int(receipt["start_d8"])
        receipt_end = int(receipt["end_d8_exclusive"])
        receipt_rows = int(receipt["rows"])
        receipt_sessions = int(receipt["sessions"])
        receipt_ready = int(receipt["ready"])
        receipt_missing = int(receipt["missing"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("QRE2 forecast receipt counts/window invalid") from exc
    if ((receipt_start, receipt_end) != (start_d8, end_d8)
            or receipt_rows != len(raw_rows)
            or receipt_rows != receipt_sessions * len(FORECAST_SEGMENTS)
            or receipt_ready + receipt_missing != receipt_rows):
        raise C.EntryV2Refusal("QRE2 forecast receipt denominator mismatch")
    source_hashes = receipt.get("source_hashes")
    if not isinstance(source_hashes, dict) or set(source_hashes) != {
            "event_manifest_sha256", "locks_sha256", "phase_schedule_sha256"}:
        raise C.EntryV2Refusal("QRE2 forecast source receipt mismatch")
    for name, value in source_hashes.items():
        _sha(value, f"forecast {name}")
    evaluation = receipt.get("evaluation")
    if (not isinstance(evaluation, dict)
            or evaluation.get("schema") != "QRE2FORECASTEVAL4"
            or int(evaluation.get("rows", -1)) != receipt_rows
            or not 0 <= int(evaluation.get("valid_rows", -1)) <= receipt_rows
            or evaluation.get("consumer_law") != (
                "diagnostics-only hindsight plane; live QRE2ForecastProvider "
                "must not open it")):
        raise C.EntryV2Refusal("QRE2 forecast evaluation receipt mismatch")
    _sha(evaluation.get("output_sha256"), "forecast evaluation output")

    parsed: dict[tuple[str, int, str], ForecastSegmentSnapshot] = {}
    lineage: list[str] = []
    ready_count = 0
    missing_count = 0
    prior_key: tuple[int, int] | None = None
    for raw in raw_rows:
        if raw["asset"] != item.asset:
            raise C.EntryV2Refusal("QRE2 forecast row asset mismatch")
        d8 = _int(raw, "d8")
        C.guard_date(d8)
        if not start_d8 <= d8 < end_d8:
            raise C.EntryV2Refusal("QRE2 forecast row outside artifact window")
        try:
            segment_index = FORECAST_SEGMENTS.index(raw["segment"])
        except ValueError as exc:
            raise C.EntryV2Refusal("unknown QRE2 forecast segment") from exc
        key_order = (d8, segment_index)
        if prior_key is not None and key_order <= prior_key:
            raise C.EntryV2Refusal("QRE2 forecast rows are not strictly ordered")
        prior_key = key_order
        if _int(raw, "history_end_d8") >= d8 or _int(raw, "fit_month") != d8 // 100:
            raise C.EntryV2Refusal("QRE2 forecast history/fit clock mismatch")
        availability = _int(raw, "availability_ts_ns")
        if availability <= 0:
            raise C.EntryV2Refusal("QRE2 forecast availability is invalid")
        for hash_name in (
                "phase_profile_sha256", "model_sha256",
                "history_source_sha256", "lineage_sha256"):
            _sha(raw[hash_name], f"forecast {hash_name}")
        if _forecast_lineage(raw, law_sha) != raw["lineage_sha256"]:
            raise C.EntryV2Refusal("QRE2 forecast row lineage mismatch")

        status, reason = raw["status"], raw["missing_reason"]
        sigma = _forecast_optional(raw, "sigma_hat_usd")
        sigma_raw = _forecast_optional(raw, "sigma_raw_hat_usd")
        sigma_persistence = _forecast_optional(raw, "sigma_persistence_usd")
        sigma_calibration_ratio = _forecast_optional(
            raw, "sigma_calibration_ratio")
        n_sigma_calibration = _int(raw, "n_sigma_calibration")
        range_hat = _forecast_optional(raw, "range_hat_usd")
        ratio = _forecast_optional(raw, "rv5_over_rv66")
        unscaled = tuple(_forecast_optional(raw, f"move_{q}_usd")
                         for q in FORECAST_QUANTILES)
        selected = tuple(_forecast_optional(raw, f"move_rs_{q}_usd")
                         for q in FORECAST_QUANTILES)
        ladder, regime = raw["ladder_source"], raw["regime_tag"]
        n_calibration = _int(raw, "n_calibration")
        n_regime_calibration = _int(raw, "n_regime_calibration")
        if (not 0 <= n_calibration <= 250
                or not 0 <= n_regime_calibration <= n_calibration):
            raise C.EntryV2Refusal("QRE2 forecast calibration count invariant failed")
        design = tuple(_forecast_optional(raw, name) for name in (
            "rv1_usd", "rv5_usd", "rv22_usd", "prior_parkinson_usd",
            "prior_gk_usd", "prior_rs_usd", "prior_jump_usd"))
        if status == "READY":
            ready_count += 1
            if (reason != "NONE" or any(value is None for value in design)
                    or sigma_raw is None or sigma_raw <= 0.0
                    or sigma_persistence is None or sigma_persistence <= 0.0
                    or sigma_calibration_ratio is None
                    or sigma_calibration_ratio <= 0.0
                    or not 0 <= n_sigma_calibration <= 66
                    or sigma is None or sigma <= 0.0
                    or range_hat is None or range_hat <= 0.0
                    or _int(raw, "n_train_range") < 250
                    or _int(raw, "n_train_sigma") < 250
                    or _int(raw, "rank_range") != 12
                    or _int(raw, "rank_sigma") != 12
                    or sigma != sigma_raw * sigma_calibration_ratio
                    or ladder not in {
                        "MISSING", "REGIME", "UNSCALED_FALLBACK"}
                    or regime not in {"NA", "LOW", "MID", "HIGH"}):
                raise C.EntryV2Refusal("QRE2 READY forecast invariant failed")
            if ladder == "MISSING":
                if (n_calibration >= 30
                        or any(value is not None for value in unscaled + selected)):
                    raise C.EntryV2Refusal(
                        "QRE2 missing ladder contradicts calibration or carries values")
            else:
                if (n_calibration < 30
                        or any(value is None for value in unscaled + selected)):
                    raise C.EntryV2Refusal(
                        "QRE2 present ladder lacks calibration or values")
                if (ladder == "REGIME"
                        and (regime == "NA" or n_regime_calibration < 30)):
                    raise C.EntryV2Refusal(
                        "QRE2 regime ladder lacks prior calibration")
                if ladder == "UNSCALED_FALLBACK" and selected != unscaled:
                    raise C.EntryV2Refusal(
                        "QRE2 fallback ladder differs from unscaled ladder")
        elif status == "MISSING":
            missing_count += 1
            if (reason not in {"DESIGN_HISTORY", "MIN_TRAIN", "RANK_DEFICIENT",
                               "NONFINITE_PREDICTION"}
                    or sigma is not None or range_hat is not None
                    or sigma_raw is not None or sigma_persistence is not None
                    or sigma_calibration_ratio is not None
                    or n_sigma_calibration != 0
                    or ladder != "MISSING"
                    or any(value is not None for value in unscaled + selected)):
                raise C.EntryV2Refusal("QRE2 MISSING forecast invariant failed")
            # A present MISSING artifact row is valid causal provenance.  Its
            # possibly-known design/regime fields remain masked from students.
            sigma = range_hat = ratio = None
            sigma_raw = sigma_persistence = sigma_calibration_ratio = None
            n_sigma_calibration = None
            selected = (None,) * len(FORECAST_QUANTILES)
            regime = "NA"
        else:
            raise C.EntryV2Refusal("unknown QRE2 forecast status")
        snapshot = ForecastSegmentSnapshot(
            raw["segment"], status, availability, sigma, range_hat, selected,
            ratio, regime, ladder, raw["lineage_sha256"], sigma_raw,
            sigma_persistence, sigma_calibration_ratio,
            n_sigma_calibration)
        parsed[(item.asset, d8, raw["segment"])] = snapshot
        lineage.append(raw["lineage_sha256"])

    if (ready_count, missing_count) != (receipt_ready, receipt_missing):
        raise C.EntryV2Refusal("QRE2 forecast READY/MISSING receipt mismatch")
    expected_lineage = hashlib.sha256(
        ("QRE2FORECASTLINEAGES4" + "".join(f"|{value}" for value in lineage)).encode()
    ).hexdigest()
    if receipt.get("lineage_aggregate_sha256") != expected_lineage:
        raise C.EntryV2Refusal("QRE2 forecast aggregate lineage mismatch")
    if len(parsed) != len(raw_rows):
        raise C.EntryV2Refusal("duplicate QRE2 forecast key")
    for index in range(0, len(raw_rows), len(FORECAST_SEGMENTS)):
        block = raw_rows[index:index + len(FORECAST_SEGMENTS)]
        if len(block) != len(FORECAST_SEGMENTS) or tuple(
                row["segment"] for row in block) != FORECAST_SEGMENTS or len(
                    {row["d8"] for row in block}) != 1:
            raise C.EntryV2Refusal("QRE2 forecast does not have four rows per lock")
    return parsed, law_sha


@dataclass(frozen=True, slots=True)
class _CorpusMergeProvenance:
    """Raw receipt inputs retained only until deterministic asset-lane merge."""

    candidate_ids_seen: tuple[str, ...]
    candidate_receipt_hashes: tuple[str, ...]
    teacher_receipt_hashes: tuple[str, ...]
    sidecar_hashes: tuple[str, ...]
    forecast_lineage: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntryCorpus:
    sessions: tuple[EntrySessionSpec, ...]
    teacher: TeacherStore
    replay: ReplayCalibrationData
    raw_prefix_fidelity: RawPrefixFidelityEvidence
    teacher_alignment: TeacherAlignmentEvidence
    candidate_feature_schema: tuple[str, ...]
    receipt: Mapping[str, Any]
    model_input_binding: ModelInputBinding
    _merge_provenance: _CorpusMergeProvenance


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


class TeacherAlignmentRefusal(C.EntryV2Refusal):
    """Production refusal that preserves the exact failed join evidence."""

    def __init__(self, message: str, evidence: TeacherAlignmentEvidence) -> None:
        super().__init__(message)
        self.evidence = evidence


def _prefix_sha256(pack: EventPack, cutoff: int) -> str:
    """Independent single-prefix reference retained for tests/debug only."""
    return prefix_sha256(pack, cutoff)


def _forecast_vintage_features(
    current: ForecastSegmentSnapshot,
    history: Sequence[ForecastSegmentSnapshot],
) -> dict[str, float]:
    """Causal daily-vintage dynamics from the pinned forecast history.

    QRE2FORECAST4 publishes at the session open.  These are therefore slopes
    across prior daily forecast vintages, not intraday revisions.  Missing
    vintages are retained in the support counts and never imputed.
    """

    records = tuple(history) + (current,)
    ready = tuple(snapshot.status == "READY" for snapshot in records)
    output: dict[str, float] = {
        "vintage_history_present": float(bool(history)),
        "vintage_ready_count_5": float(sum(ready[-5:])),
        "vintage_ready_count_22": float(sum(ready[-22:])),
    }

    def metric(snapshot: ForecastSegmentSnapshot, name: str) -> float | None:
        if snapshot.status != "READY":
            return None
        if name == "sigma":
            value = snapshot.sigma_hat_usd
        elif name == "range":
            value = snapshot.range_hat_usd
        elif name == "q50":
            value = snapshot.move_usd[2]
        elif name == "q90":
            value = snapshot.move_usd[4]
        elif name == "rv_ratio":
            value = snapshot.rv5_over_rv66
        else:  # pragma: no cover - fixed local roster
            raise AssertionError(name)
        if value is None or not math.isfinite(float(value)):
            return None
        return float(value)

    def slope(values: Sequence[float], window: int) -> float:
        selected = np.asarray(values[-window:], np.float64)
        if len(selected) < 2:
            return 0.0
        x = np.arange(len(selected), dtype=np.float64)
        centered = x - float(x.mean())
        denominator = float(np.dot(centered, centered))
        return float(np.dot(centered, selected - selected.mean()) / denominator
                     if denominator > 0.0 else 0.0)

    for name, unit in (
            ("sigma", "_usd"), ("range", "_usd"),
            ("q50", "_usd"), ("q90", "_usd"),
            ("rv_ratio", "")):
        observed = [value for snapshot in records
                    if (value := metric(snapshot, name)) is not None]
        current_value = metric(current, name)
        prior = [value for snapshot in history
                 if (value := metric(snapshot, name)) is not None]
        delta = (current_value - prior[-1]
                 if current_value is not None and prior else 0.0)
        acceleration = (current_value - 2.0 * prior[-1] + prior[-2]
                        if current_value is not None and len(prior) >= 2 else 0.0)
        stem = f"vintage_{name}"
        output.update({
            stem + f"_delta_1{unit}": float(delta),
            stem + f"_slope_5{unit}": slope(observed, 5),
            stem + f"_slope_22{unit}": slope(observed, 22),
            stem + f"_acceleration{unit}": float(acceleration),
        })

    previous_regime = next((snapshot.regime for snapshot in reversed(history)
                            if snapshot.status == "READY"
                            and snapshot.regime != "NA"), None)
    current_regime = current.regime if current.status == "READY" else "NA"
    persistence = 0
    if current_regime != "NA":
        persistence = 1
        for snapshot in reversed(history):
            if snapshot.status != "READY" or snapshot.regime != current_regime:
                break
            persistence += 1
    output.update({
        "vintage_regime_changed": float(
            previous_regime is not None and current_regime != "NA"
            and previous_regime != current_regime),
        "vintage_regime_persistence": float(persistence),
    })
    return output


def _forecast_features(provider: ForecastProvider, query: ForecastQuery,
                       ) -> tuple[dict[str, float], str]:
    receipt = _sha(getattr(provider, "receipt_sha256", ""), "forecast receipt")
    row = provider.forecast(query)
    if row is None:
        raise C.EntryV2Refusal(f"forecast row missing: {query.candidate_id}")
    row.validate(query)
    out: dict[str, float] = {}
    history_lineage: dict[str, tuple[str, ...]] = {}
    for scope, snapshot in (("session", row.session),
                            ("phase", row.phase_segment)):
        present = snapshot.status == "READY"
        ladder_present = present and snapshot.ladder_source != "MISSING"
        ratio_present = present and snapshot.rv5_over_rv66 is not None
        regime_present = present and snapshot.regime != "NA"
        values = {
            "forecast_age_sec": (
                (query.decision_ts_ns - snapshot.availability_ts_ns)
                / 1_000_000_000.0) if present else 0.0,
            "sigma_hat_usd": float(snapshot.sigma_hat_usd) if present else 0.0,
            "range_hat_usd": float(snapshot.range_hat_usd) if present else 0.0,
            "sigma_components_present": float(
                present and snapshot.sigma_raw_hat_usd is not None),
            "sigma_raw_hat_usd": (
                float(snapshot.sigma_raw_hat_usd)
                if present and snapshot.sigma_raw_hat_usd is not None else 0.0),
            "sigma_persistence_usd": (
                float(snapshot.sigma_persistence_usd)
                if present and snapshot.sigma_persistence_usd is not None else 0.0),
            "sigma_calibration_ratio": (
                float(snapshot.sigma_calibration_ratio)
                if present and snapshot.sigma_calibration_ratio is not None else 0.0),
            "sigma_calibration_count": (
                float(snapshot.n_sigma_calibration)
                if present and snapshot.n_sigma_calibration is not None else 0.0),
            "sigma_calibrated_hat_usd": (
                float(snapshot.sigma_raw_hat_usd)
                * float(snapshot.sigma_calibration_ratio)
                if present and snapshot.sigma_raw_hat_usd is not None
                and snapshot.sigma_calibration_ratio is not None else 0.0),
            "sigma_shrinkage_delta_usd": (
                float(snapshot.sigma_hat_usd)
                - float(snapshot.sigma_raw_hat_usd)
                if present and snapshot.sigma_raw_hat_usd is not None else 0.0),
            "sigma_ols_minus_persistence_usd": (
                float(snapshot.sigma_raw_hat_usd)
                - float(snapshot.sigma_persistence_usd)
                if present and snapshot.sigma_raw_hat_usd is not None
                and snapshot.sigma_persistence_usd is not None else 0.0),
            "sigma_ols_over_persistence": (
                float(snapshot.sigma_raw_hat_usd)
                / float(snapshot.sigma_persistence_usd)
                if present and snapshot.sigma_raw_hat_usd is not None
                and snapshot.sigma_persistence_usd is not None
                and float(snapshot.sigma_persistence_usd) > 0.0 else 0.0),
            **{
                f"move_{quantile}_usd": (
                    float(value) if ladder_present else 0.0)
                for quantile, value in zip(FORECAST_QUANTILES, snapshot.move_usd)
            },
            "rv5_over_rv66": (
                float(snapshot.rv5_over_rv66) if ratio_present else 0.0),
            "rv5_over_rv66_present": float(ratio_present),
            "regime_low_present": float(regime_present and snapshot.regime == "LOW"),
            "regime_mid_present": float(regime_present and snapshot.regime == "MID"),
            "regime_high_present": float(regime_present and snapshot.regime == "HIGH"),
            "regime_present": float(regime_present),
            "move_ladder_present": float(ladder_present),
            "unscaled_fallback_present": float(
                present and snapshot.ladder_source == "UNSCALED_FALLBACK"),
            "forecast_present": float(present),
        }
        history = provider.forecast_history(
            query.asset, query.trading_day, snapshot.segment,
            query.decision_ts_ns, 22)
        if any(int(item.availability_ts_ns) >= int(query.decision_ts_ns)
               for item in history):
            raise C.EntryV2Refusal("forecast history is not strictly prior")
        values.update(_forecast_vintage_features(snapshot, history))
        history_lineage[scope] = tuple(item.lineage_sha256 for item in history)
        for name in FORECAST_SCOPE_FIELDS:
            out[f"{scope}_{name}"] = values[name]
    row_lineage = C.object_sha256({
        "schema": "entry-v2-candidate-forecast-join-v2",
        "provider_receipt_sha256": receipt,
        "candidate_id": row.candidate_id,
        "asset": row.asset,
        "trading_day": row.trading_day,
        "decision_ts_ns": row.decision_ts_ns,
        "phase": row.phase,
        "feature_fields": list(FORECAST_FEATURE_FIELDS),
        "feature_values": [out[name] for name in FORECAST_FEATURE_FIELDS],
        "session": _forecast_snapshot_payload(row.session),
        "phase_segment": _forecast_snapshot_payload(row.phase_segment),
        "history_lineage": history_lineage,
        "source_sha256": row.source_sha256,
    })
    return out, row_lineage


def _candidate_features(row: Mapping[str, str], forecast: Mapping[str, float],
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
        **{f"rung_{index}_present": float(bool(rung & (1 << index)))
           for index in range(4)},
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


def _horizon_targets(pack: EventPack, row: Mapping[str, str],
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
            gross = (side * (mid2 - entry_mid2) * 0.5 * RAW_PRICE_SCALE
                     * multiplier)
            value = gross - frozen_cost
            if not math.isfinite(value):
                raise C.EntryV2Refusal("self-supervised horizon value is non-finite")
            values[column], valid[column] = value, True
            if horizon == 60:
                # Three exact future-tape bits form an 8-class micro-phase:
                # midpoint up, spread wider, and bid-size dominance.  The row
                # remains target-only and is never copied into causal features.
                entry_spread = (_int(row, "entry_ask_px")
                                - _int(row, "entry_bid_px"))
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


def _session_receipt(raw: bytes, *, schema: str, asset: str, d8: int,
                     output_sha: str, expected_rows: int, name: str,
                     ) -> Mapping[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid {name} JSON") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise C.EntryV2Refusal(f"{name} schema mismatch")
    if (value.get("asset"), value.get("d8"), value.get("rows"),
            value.get("output_sha256")) != (asset, d8, expected_rows, output_sha):
        raise C.EntryV2Refusal(f"{name} identity/count/output mismatch")
    try:
        start = int(value["start_d8"])
        end = int(value["end_d8_exclusive"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal(f"{name} has an invalid record window") from exc
    C.guard_decode_window(start, end)
    if value.get("holdout_start_d8") != C.HOLDOUT_START_D8 or value.get(
            "final_exam_permit") is not False:
        raise C.EntryV2Refusal(f"{name} holdout contract mismatch")
    return value


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
    """Build the verified development corpus without opening any holdout row."""
    resolved_maximum_d8 = (
        C.DEVELOPMENT_END_D8 if maximum_d8 is None else int(maximum_d8)
    )
    C.guard_date(resolved_maximum_d8)
    if resolved_maximum_d8 > C.DEVELOPMENT_END_D8:
        raise C.EntryV2Refusal("corpus maximum exceeds the development window")
    resolved_minimum_d8 = (
        None if minimum_d8_exclusive is None else int(minimum_d8_exclusive)
    )
    if resolved_minimum_d8 is not None:
        C.guard_date(resolved_minimum_d8)
        if resolved_minimum_d8 >= resolved_maximum_d8:
            raise C.EntryV2Refusal("corpus chronological interval is empty/reversed")
    required = {str(asset).upper() for asset in require_assets}
    by_asset = {item.asset: item for item in artifacts}
    if len(by_asset) != len(artifacts) or set(by_asset) != required:
        raise C.EntryV2Refusal(
            f"artifact assets must be exactly {sorted(required)}, got {sorted(by_asset)}"
        )
    provider: ForecastProvider
    if isinstance(forecasts, Sequence):
        if not allow_test_forecast_adapter:
            raise C.EntryV2Refusal(
                "explicit forecast rows are a test-only adapter; use QRE2ForecastProvider")
        provider = ExplicitForecastRows(tuple(forecasts))
    elif isinstance(forecasts, ForecastProvider):
        if _is_test_forecast_provider(
                forecasts) and not allow_test_forecast_adapter:
            raise C.EntryV2Refusal(
                "explicit forecast rows are a test-only adapter; use QRE2ForecastProvider")
        provider = forecasts
    else:
        raise C.EntryV2Refusal("a typed forecast provider or explicit rows are required")
    _sha(getattr(provider, "receipt_sha256", ""), "forecast receipt")
    if set(getattr(provider, "assets", ())) != required:
        raise C.EntryV2Refusal(
            f"forecast provider assets must be exactly {sorted(required)}")

    examples_by_session: dict[SessionRef, list[CausalEntryExample]] = {}
    feature_by_id: dict[str, tuple[float, ...]] = {}
    target_by_id: dict[str, tuple[np.ndarray, np.ndarray, int, bool]] = {}
    context_tensor_by_id: dict[str, ContextTensor] = {}
    audit_context_recorded = False
    event_source_pins: dict[SessionRef, dict[str, Any]] = {}
    teacher_paths: list[TeacherPath] = []
    outcomes: dict[str, ReplayOutcome] = {}
    expected_sessions: list[SessionRef] = []
    expected_session_open_ns: dict[tuple[str, int], int] = {}
    candidate_ids_seen: set[str] = set()
    prefix_events = 0
    prefix_unique_cutoffs = 0
    prefix_bytes_hashed = 0
    clear_expected = 0
    clear_joined = 0
    clear_ready = 0
    clear_typed_no_sane_suffix = 0
    compliance_counts = {"CLEAR": 0, "PROHIBITED": 0, "COMPLIANCE_UNKNOWN": 0}
    sidecar_hashes: list[str] = []
    candidate_receipt_hashes: list[str] = []
    teacher_receipt_hashes: list[str] = []
    context_receipts: dict[str, str] = {}
    forecast_lineage: list[str] = []
    artifact_receipts: list[dict[str, Any]] = []
    observed_manifest_days: list[int] = []
    verified_session_warm_hits = 0
    verified_session_cold_publishes = 0
    model_array_bytes_materialized = 0
    model_array_bytes_reused = 0
    physical_full_pack_opens = 0
    model_array_physical_fills = 0
    full_authorities: list[dict[str, Any]] = []
    excluded_non_trading_calendar_rows = {asset: 0 for asset in required}
    excluded_outside_asset_coverage_rows = {asset: 0 for asset in required}
    excluded_full_closure_rows = {asset: 0 for asset in required}
    durable_store = None if array_cache is None else array_cache.durable_store
    if require_durable_window and durable_store is None:
        raise C.EntryV2Refusal(
            "strict durable corpus reconstruction requires the durable store"
        )

    for asset in sorted(required):
        if cancel_event is not None and cancel_event.is_set():
            raise C.EntryV2Refusal("asset corpus construction was cancelled")
        item = by_asset[asset]
        root = item.root
        context_repo = context_repositories.get(asset)
        if context_repo is None or context_repo.asset != asset:
            raise C.EntryV2Refusal(f"causal context repository missing/misaligned: {asset}")
        context_receipts[asset] = _embedded_receipt(
            context_repo.receipt, f"{asset} context receipt")

        candidate_manifest_path = root / "g1" / "candidates" / asset / "manifest.tsv"
        teacher_manifest_path = root / "g1" / "teacher" / asset / "manifest.tsv"
        candidate_manifest_raw = _read_pinned(
            candidate_manifest_path, item.candidate_manifest_sha256,
            f"{asset} candidate manifest")
        teacher_manifest_raw = _read_pinned(
            teacher_manifest_path, item.teacher_manifest_sha256,
            f"{asset} teacher manifest")
        candidate_manifest = _table(
            candidate_manifest_raw, "QRE2G1CANDMAN2", _CANDIDATE_MANIFEST_COLUMNS,
            f"{asset} candidate manifest")
        teacher_manifest = _table(
            teacher_manifest_raw, "QRE2G1TEACHMAN2", _TEACHER_MANIFEST_COLUMNS,
            f"{asset} teacher manifest")
        if [row["d8"] for row in candidate_manifest] != [row["d8"] for row in teacher_manifest]:
            raise C.EntryV2Refusal(f"{asset} candidate/teacher session manifests differ")

        candidate_aggregate_raw = _read_pinned(
            root / "g1" / "receipts" / f"{asset}.candidates.json",
            item.candidate_receipt_sha256, f"{asset} candidate aggregate receipt")
        teacher_aggregate_raw = _read_pinned(
            root / "g1" / "receipts" / f"{asset}.teacher.json",
            item.teacher_receipt_sha256, f"{asset} teacher aggregate receipt")
        candidate_aggregate = _json_receipt(
            candidate_aggregate_raw, schema="QRE2G1CANDRECEIPT2", stage="candidates",
            asset=asset, manifest_sha256=item.candidate_manifest_sha256,
            name=f"{asset} candidate aggregate receipt")
        teacher_aggregate = _json_receipt(
            teacher_aggregate_raw, schema="QRE2G1TEACHRECEIPT2", stage="teacher",
            asset=asset, manifest_sha256=item.teacher_manifest_sha256,
            name=f"{asset} teacher aggregate receipt")
        event_manifest_path = root / "events" / asset / "manifest.tsv"
        event_manifest_sha256 = C.file_sha256(event_manifest_path)
        expected_teacher_auxiliary = hashlib.sha256((
            item.candidate_manifest_sha256 + "\n" + event_manifest_sha256
        ).encode()).hexdigest()
        if teacher_aggregate.get("auxiliary_sha256") != expected_teacher_auxiliary:
            raise C.EntryV2Refusal(
                "teacher aggregate candidate/event authority pin mismatch"
            )
        if int(candidate_aggregate.get("sessions", -1)) != len(candidate_manifest):
            raise C.EntryV2Refusal("candidate aggregate session count mismatch")
        if int(teacher_aggregate.get("sessions", -1)) != len(teacher_manifest):
            raise C.EntryV2Refusal("teacher aggregate session count mismatch")
        candidate_count = sum(_int(row, "rows") for row in candidate_manifest)
        no_candidate_sessions = sum(
            _int(row, "rows") == 0 for row in candidate_manifest
        )
        teacher_count = sum(_int(row, "rows") for row in teacher_manifest)
        teacher_ready_count = sum(_int(row, "ready") for row in teacher_manifest)
        teacher_refused_count = sum(_int(row, "refused") for row in teacher_manifest)
        if (int(candidate_aggregate.get("candidates", -1)) != candidate_count
                or int(candidate_aggregate.get("no_candidate_sessions", -1))
                    != no_candidate_sessions):
            raise C.EntryV2Refusal("candidate aggregate row counts mismatch")
        if (int(teacher_aggregate.get("candidates", -1)) != teacher_count
                or int(teacher_aggregate.get("teacher_ready", -1))
                    != teacher_ready_count
                or int(teacher_aggregate.get("teacher_refused", -1))
                    != teacher_refused_count
                or teacher_ready_count + teacher_refused_count != teacher_count):
            raise C.EntryV2Refusal("teacher aggregate typed row counts mismatch")

        candidate_window = (
            int(candidate_aggregate["start_d8"]),
            int(candidate_aggregate["end_d8_exclusive"]),
        )
        teacher_window = (
            int(teacher_aggregate["start_d8"]),
            int(teacher_aggregate["end_d8_exclusive"]),
        )
        if candidate_window != teacher_window:
            raise C.EntryV2Refusal("candidate/teacher aggregate windows differ")
        # Validate the complete manifest roster and its declared counts before
        # choosing the chronological materialization prefix.  No referenced
        # path is resolved, stated or opened by this authority-only pass.
        full_days: list[int] = []
        for cm, tm in zip(candidate_manifest, teacher_manifest):
            d8 = _int(cm, "d8")
            C.guard_date(d8)
            if cm["asset"] != asset or tm["asset"] != asset or _int(tm, "d8") != d8:
                raise C.EntryV2Refusal("manifest asset/date mismatch")
            if cm["status"] not in {
                    "READY", "NO_ATR14", "NO_LOCK", "NO_EVENTS", "NO_SANE_BBO"}:
                raise C.EntryV2Refusal("unknown candidate session status")
            if any(_int(cm, name) < 0 for name in (
                    "rows", "raw_events", "two_sided_events", "sane_events")):
                raise C.EntryV2Refusal("candidate manifest count is negative")
            if any(_int(tm, name) < 0 for name in ("rows", "ready", "refused")):
                raise C.EntryV2Refusal("teacher manifest count is negative")
            if _int(tm, "ready") + _int(tm, "refused") != _int(tm, "rows"):
                raise C.EntryV2Refusal("teacher manifest typed row counts mismatch")
            if cm["candidate_sha256"] != tm["candidate_sha256"]:
                raise C.EntryV2Refusal("teacher manifest candidate hash mismatch")
            full_days.append(d8)
        if full_days != sorted(full_days) or len(full_days) != len(set(full_days)):
            raise C.EntryV2Refusal("manifest days are not strictly chronological")
        if maximum_d8 is not None and resolved_maximum_d8 not in full_days:
            raise C.EntryV2Refusal("explicit corpus maximum is absent from manifest roster")
        full_authorities.append({
            "asset": asset,
            "record_start_d8": candidate_window[0],
            "record_end_d8_exclusive": candidate_window[1],
            "candidate_manifest_sha256": item.candidate_manifest_sha256,
            "teacher_manifest_sha256": item.teacher_manifest_sha256,
            "event_manifest_sha256": event_manifest_sha256,
            "candidate_aggregate_receipt_sha256": item.candidate_receipt_sha256,
            "teacher_aggregate_receipt_sha256": item.teacher_receipt_sha256,
            "full_manifest_sessions": len(candidate_manifest),
            "full_manifest_candidates": candidate_count,
            "full_manifest_teacher_rows": teacher_count,
        })

        lock_by_d8: dict[int, Mapping[str, str]] | None = None
        locks_sha256: str | None = None
        for session_ordinal, (cm, tm) in enumerate(
            zip(candidate_manifest, teacher_manifest)
        ):
            if cancel_event is not None and cancel_event.is_set():
                raise C.EntryV2Refusal("asset corpus construction was cancelled")
            d8 = _int(cm, "d8")
            C.guard_date(d8)  # wall before any referenced session payload
            if cm["asset"] != asset or tm["asset"] != asset or _int(tm, "d8") != d8:
                raise C.EntryV2Refusal("manifest asset/date mismatch")
            session_status = cm["status"]
            if session_status not in {
                    "READY", "NO_ATR14", "NO_LOCK", "NO_EVENTS", "NO_SANE_BBO"}:
                raise C.EntryV2Refusal("unknown candidate session status")
            if (d8 > resolved_maximum_d8
                    or (resolved_minimum_d8 is not None
                        and d8 <= resolved_minimum_d8)):
                continue
            observed_manifest_days.append(d8)
            session = SessionRef(asset, d8, f"{asset}-{d8}")
            verified_product = None
            verified_semantic: Mapping[str, Any] | None = None
            verified_identity = _verified_session_identity(asset, d8, cm, tm)
            if durable_store is not None:
                verified_product = durable_store.load(
                    "verified-sessions", verified_identity,
                    VERIFIED_SESSION_LAW_SHA256,
                )
            verified_hit = verified_product is not None
            if require_durable_window and not verified_hit:
                # The isolated cold producer must publish the complete semantic
                # session (candidate/teacher bytes, arrays and diagnostic plane)
                # before the parent reconstructs it.  Falling through here would
                # silently turn a missing/corrupt worker result into a second QRE2
                # open in the parent and defeat both the speed and one-open laws.
                raise C.EntryV2Refusal(
                    "strict durable corpus session is absent; parent rebuild forbidden"
                )
            if verified_hit:
                verified_session_warm_hits += 1
                assert verified_product is not None
                verified_semantic = verified_product.receipt.get("semantic")
                verified_producer = verified_product.receipt.get("producer")
                if (not isinstance(verified_semantic, Mapping)
                        or verified_semantic.get("schema")
                            != "entry-v2-verified-session-map-v1"
                        or len(verified_product.arrays) != 8
                        or not isinstance(verified_producer, Mapping)
                        or verified_producer.get("schema")
                            != "entry-v2-verified-session-producer-v1"
                        or int(verified_producer.get(
                            "physical_full_pack_opens", -1))
                            != (1 if cm["event_pack_sha256"] != "ABSENT" else 0)
                        or int(verified_producer.get(
                            "model_array_physical_fills", -1))
                            != (1 if cm["event_pack_sha256"] != "ABSENT"
                                and int(cm["rows"]) > 0 else 0)
                        or verified_producer.get("candidate_payload_reads") != 1
                        or verified_producer.get("teacher_payload_reads") != 1):
                    verified_product.close()
                    raise C.EntryV2Refusal(
                        "verified-session durable semantic differs"
                    )
                candidate_raw, teacher_raw, candidate_receipt_raw, \
                    teacher_receipt_raw = (
                        np.asarray(value, np.uint8).tobytes()
                        for value in verified_product.arrays[:4]
                    )
                candidate_relative = Path(cm["candidate_file"])
                teacher_relative = Path(tm["teacher_file"])
                for relative in (candidate_relative, teacher_relative):
                    _guard_path_before_open(relative)
                    if relative.is_absolute() or ".." in relative.parts:
                        verified_product.close()
                        raise C.EntryV2Refusal(
                            "verified-session payload path escapes substrate"
                        )
                candidate_path = root / candidate_relative
                teacher_path = root / teacher_relative
            else:
                candidate_path = _under(root, cm["candidate_file"], d8)
                teacher_path = _under(root, tm["teacher_file"], d8)
                candidate_raw = _read_pinned(
                    candidate_path, cm["candidate_sha256"], "candidate session")
                teacher_raw = _read_pinned(
                    teacher_path, tm["teacher_sha256"], "teacher session")
            if (hashlib.sha256(candidate_raw).hexdigest() != cm["candidate_sha256"]
                    or hashlib.sha256(teacher_raw).hexdigest()
                        != tm["teacher_sha256"]):
                if verified_product is not None:
                    verified_product.close()
                raise C.EntryV2Refusal(
                    "verified-session candidate/teacher payload hash differs"
                )
            candidate_rows = _table(candidate_raw, "QRE2G1CAND2", _CANDIDATE_COLUMNS,
                                    "candidate session", d8=d8)
            teacher_rows = _table(teacher_raw, "QRE2G1TEACH2", _TEACHER_COLUMNS,
                                  "teacher session", d8=d8)
            if len(candidate_rows) != _int(cm, "rows") or len(teacher_rows) != _int(tm, "rows"):
                raise C.EntryV2Refusal("session row count differs from manifest")
            if session_status == "NO_LOCK" and (candidate_rows or teacher_rows):
                raise C.EntryV2Refusal("NO_LOCK session carries candidate/teacher rows")
            if cm["candidate_sha256"] != tm["candidate_sha256"]:
                raise C.EntryV2Refusal("teacher manifest candidate hash mismatch")

            if not verified_hit:
                candidate_receipt_raw = _read_pinned(
                    _under(root, cm["receipt_file"], d8), cm["receipt_sha256"],
                    "candidate session receipt")
                teacher_receipt_raw = _read_pinned(
                    _under(root, tm["receipt_file"], d8), tm["receipt_sha256"],
                    "teacher session receipt")
            if (hashlib.sha256(candidate_receipt_raw).hexdigest()
                    != cm["receipt_sha256"]
                    or hashlib.sha256(teacher_receipt_raw).hexdigest()
                        != tm["receipt_sha256"]):
                if verified_product is not None:
                    verified_product.close()
                raise C.EntryV2Refusal(
                    "verified-session receipt payload hash differs"
                )
            candidate_receipt = _session_receipt(
                candidate_receipt_raw, schema="QRE2G1CANDRECEIPT2", asset=asset,
                d8=d8, output_sha=cm["candidate_sha256"],
                expected_rows=len(candidate_rows), name="candidate session receipt")
            teacher_receipt = _session_receipt(
                teacher_receipt_raw, schema="QRE2G1TEACHRECEIPT2", asset=asset,
                d8=d8, output_sha=tm["teacher_sha256"],
                expected_rows=len(teacher_rows), name="teacher session receipt")
            candidate_receipt_hashes.append(cm["receipt_sha256"])
            teacher_receipt_hashes.append(tm["receipt_sha256"])
            if teacher_receipt.get("source_hashes", {}).get(
                    "candidate_sha256") != cm["candidate_sha256"]:
                raise C.EntryV2Refusal("teacher receipt candidate pin mismatch")

            source_hashes = candidate_receipt.get("source_hashes")
            if not isinstance(source_hashes, Mapping):
                raise C.EntryV2Refusal("candidate receipt source hashes missing")
            row_locks_sha = _sha(
                source_hashes.get("locks_sha256"), "candidate locks manifest"
            )
            if lock_by_d8 is None:
                locks_sha256 = row_locks_sha
                lock_raw = _read_pinned(
                    root / "locks" / f"{asset}.tsv",
                    row_locks_sha,
                    f"{asset} lock manifest",
                )
                lock_rows = _table(
                    lock_raw, "QRE2LOCK2", _LOCK_COLUMNS,
                    f"{asset} lock manifest",
                )
                if [row["d8"] for row in lock_rows] != [
                    row["d8"] for row in candidate_manifest
                ]:
                    raise C.EntryV2Refusal(
                        f"{asset} lock/candidate session rosters differ"
                    )
                lock_by_d8 = {_int(row, "d8"): row for row in lock_rows}
            elif row_locks_sha != locks_sha256:
                raise C.EntryV2Refusal(
                    "candidate session receipts disagree on the lock manifest"
                )
            lock = lock_by_d8.get(d8)
            if lock is None or lock["asset"] != asset:
                raise C.EntryV2Refusal("candidate session has no matching lock row")
            lock_status = lock["status"]
            if lock_status not in {
                "LOCKED", "WARMUP_NO_PREVIOUS", "REFUSED_PREVIOUS_NO_OUTRIGHT"
            }:
                raise C.EntryV2Refusal("lock row has an unknown status")
            lock_open_utc = _int(lock, "open_utc")
            lock_close_utc = _int(lock, "close_utc")
            if lock_open_utc <= 0 or lock_close_utc <= lock_open_utc:
                raise C.EntryV2Refusal("lock row has an invalid session clock")
            if (lock_status == "LOCKED") != (session_status != "NO_LOCK"):
                raise C.EntryV2Refusal(
                    "candidate NO_LOCK status disagrees with the lock manifest"
                )
            if lock_status == "WARMUP_NO_PREVIOUS":
                if session_ordinal != 0:
                    raise C.EntryV2Refusal(
                        "only the explicit initial prior-lock warmup is excludable"
                    )
            elif C.denominator_disposition(asset, d8) == (
                    "OUTSIDE_ASSET_COVERAGE"):
                if candidate_rows or teacher_rows:
                    raise C.EntryV2Refusal(
                        "OUTSIDE_ASSET_COVERAGE row carries candidate/teacher rows"
                    )
                excluded_outside_asset_coverage_rows[asset] += 1
            elif not C.is_globex_trading_day(d8):
                if candidate_rows or teacher_rows:
                    raise C.EntryV2Refusal(
                        "non-trading calendar row carries candidate/teacher rows"
                    )
                excluded_non_trading_calendar_rows[asset] += 1
            elif not C.is_denominator_day(asset, d8):
                if C.denominator_disposition(asset, d8) != "FULL_CLOSE":
                    raise C.EntryV2Refusal(
                        "QRE2CAL1 excluded an untyped asset-day"
                    )
                if candidate_rows or teacher_rows:
                    raise C.EntryV2Refusal(
                        "FULL_CLOSE row carries candidate/teacher rows"
                    )
                excluded_full_closure_rows[asset] += 1
            else:
                # Later lock failures, provider outages, empty sessions, and
                # no-candidate sessions are eligible zero-dollar denominator
                # units.  Only WARMUP_NO_PREVIOUS above is excluded.
                expected_sessions.append(session)
                expected_session_open_ns[(asset, d8)] = (
                    lock_open_utc * 1_000_000_000
                )

            event_hash = cm["event_pack_sha256"]
            pack: EventPack | None = None
            if event_hash != "ABSENT":
                _sha(event_hash, "event pack")
                expected_teacher_event = event_hash if teacher_rows else "ABSENT"
                if tm["event_pack_sha256"] != expected_teacher_event:
                    raise C.EntryV2Refusal("candidate/teacher event pack pins differ")
                if verified_hit:
                    assert verified_product is not None
                    assert verified_semantic is not None
                    source_pin = dict(verified_semantic.get("source_pin", {}))
                    event_path = Path(str(source_pin.pop("qre2_path", "")))
                    prefix_raw = np.asarray(verified_product.arrays[4], np.uint8)
                    if (prefix_raw.ndim != 1
                            or prefix_raw.nbytes % EVENT_DTYPE.itemsize
                            or not event_path.is_absolute()):
                        verified_product.close()
                        raise C.EntryV2Refusal(
                            "verified-session prefix/source descriptor differs"
                        )
                    prefix_rows = prefix_raw.view(EVENT_DTYPE)
                    source_pin["qre2_path"] = event_path
                    pack = _VerifiedPackView(
                        event_path, prefix_rows, source_pin, event_hash
                    )
                    post_hash_stat = SimpleNamespace(
                        st_size=int(source_pin["source_size_bytes"]),
                        st_dev=int(source_pin["source_device"]),
                        st_ino=int(source_pin["source_inode"]),
                        st_mtime_ns=int(source_pin["source_mtime_ns"]),
                        st_ctime_ns=int(source_pin["source_ctime_ns"]),
                    )
                    sidecar_sha256 = str(source_pin["sidecar_sha256"])
                    sidecar_hashes.append(sidecar_sha256)
                else:
                    event_path = _under(root, f"events/{asset}/{d8}.qre2", d8)
                    pre_hash_stat = event_path.stat()
                    pack = EventPack(event_path, verify_hash=True)
                    post_hash_stat = event_path.stat()
                    if (
                        pre_hash_stat.st_size, pre_hash_stat.st_dev,
                        pre_hash_stat.st_ino, pre_hash_stat.st_mtime_ns,
                        pre_hash_stat.st_ctime_ns,
                    ) != (
                        post_hash_stat.st_size, post_hash_stat.st_dev,
                        post_hash_stat.st_ino, post_hash_stat.st_mtime_ns,
                        post_hash_stat.st_ctime_ns,
                    ):
                        pack.close()
                        raise C.EntryV2Refusal(
                            "QRE2 source changed during trust-boundary hash")
                if pack.header.asset != asset or pack.header.d8 != d8:
                    pack.close()
                    raise C.EntryV2Refusal("event pack identity differs from manifest")
                if pack.header.n_events != _int(cm, "raw_events"):
                    pack.close()
                    raise C.EntryV2Refusal("event count differs from candidate manifest")
                if pack.sidecar.get("schema") != "QRE2EVENTMETA2":
                    pack.close()
                    raise C.EntryV2Refusal("event sidecar schema mismatch")
                if pack.sidecar.get("event_pack_sha256") != event_hash:
                    pack.close()
                    raise C.EntryV2Refusal("event sidecar hash pin mismatch")
                window = pack.sidecar.get("record_window")
                if not isinstance(window, dict):
                    pack.close()
                    raise C.EntryV2Refusal("event sidecar record window missing")
                C.guard_decode_window(int(window.get("start_d8", 0)),
                                      int(window.get("end_d8_exclusive", 0)))
                if not verified_hit:
                    sidecar_path = event_path.with_suffix(".qre2.json")
                    sidecar_sha256 = C.file_sha256(sidecar_path)
                    sidecar_hashes.append(sidecar_sha256)
                stat = post_hash_stat
                event_source_pins[session] = {
                    "qre2_path": event_path,
                    "source_sha256": event_hash,
                    "sidecar_sha256": sidecar_sha256,
                    "asset": asset,
                    "d8": d8,
                    "locked_iid": pack.header.locked_iid,
                    "open_utc": pack.header.open_utc,
                    "close_utc": pack.header.close_utc,
                    "event_count": pack.header.n_events,
                    "source_size_bytes": stat.st_size,
                    "source_device": stat.st_dev,
                    "source_inode": stat.st_ino,
                    "source_mtime_ns": stat.st_mtime_ns,
                    "source_ctime_ns": stat.st_ctime_ns,
                }
            elif candidate_rows or teacher_rows:
                raise C.EntryV2Refusal("candidate/teacher rows have no event pack")
            elif tm["event_pack_sha256"] != "ABSENT":
                raise C.EntryV2Refusal("empty session event pack pins differ")

            candidate_ids = [row["candidate_id"] for row in candidate_rows]
            teacher_ids = [row["candidate_id"] for row in teacher_rows]
            if any(candidate_id not in set(candidate_ids) for candidate_id in teacher_ids):
                if pack is not None:
                    pack.close()
                raise C.EntryV2Refusal("teacher contains an unknown candidate identity")
            if teacher_ids != candidate_ids:
                if pack is not None:
                    pack.close()
                raise C.EntryV2Refusal(
                    "teacher rows are missing/permuted relative to candidates"
                )
            if len(candidate_ids) != len(set(candidate_ids)):
                if pack is not None:
                    pack.close()
                raise C.EntryV2Refusal("duplicate candidate_id within session")
            if len(teacher_ids) != len(set(teacher_ids)):
                if pack is not None:
                    pack.close()
                raise C.EntryV2Refusal("duplicate teacher candidate_id within session")
            teacher_by_id = {row["candidate_id"]: row for row in teacher_rows}
            if verified_hit and event_hash != "ABSENT" and not candidate_rows:
                empty_source = SessionEventSource(
                    array_cache=None, max_cutoff=0, **event_source_pins[session]
                )
                empty_source._verify_cached_header()
                empty_source.measurements.record_header_revalidation()
            verified_targets: dict[str, tuple[np.ndarray, np.ndarray, int, bool]] = {}
            if verified_hit:
                assert verified_product is not None
                assert verified_semantic is not None
                target_ids = tuple(str(value) for value in
                                   verified_semantic.get("target_candidate_ids", ()))
                # These rows survive beyond the per-session durable product:
                # ``target_by_id`` is stacked only after every session has
                # been consumed.  Own the small target planes before closing
                # the mmap at the session boundary; retaining views here is a
                # native use-after-unmap, not merely a stale Python object.
                values = np.array(
                    verified_product.arrays[5], dtype=np.float64,
                    copy=True, order="C",
                )
                valid = np.array(
                    verified_product.arrays[6], dtype=np.bool_,
                    copy=True, order="C",
                )
                phase = np.array(
                    verified_product.arrays[7], dtype=np.int64,
                    copy=True, order="C",
                )
                if (values.shape != (len(target_ids), len(HORIZONS_SECONDS))
                        or valid.shape != values.shape
                        or phase.shape != (len(target_ids), 2)
                        or len(target_ids) != len(set(target_ids))):
                    verified_product.close()
                    raise C.EntryV2Refusal(
                        "verified-session legacy target descriptor differs"
                    )
                verified_targets = {
                    candidate_id: (values[index], valid[index],
                                   int(phase[index, 0]), bool(phase[index, 1]))
                    for index, candidate_id in enumerate(target_ids)
                }

            context_rows = [
                candidate for candidate in candidate_rows
                if candidate["compliance_status"] == "CLEAR"
                and teacher_by_id[candidate["candidate_id"]]["status"] == "READY"
            ]
            if context_rows:
                batch_values, batch_type_ids, batch_valid = (
                    context_repo.tensor_batch(
                        d8,
                        (_int(candidate, "decision_ts_ns")
                         for candidate in context_rows),
                    )
                )
                series_ids = tuple(ASSET_CONTEXT_SERIES[asset])
                for index, candidate in enumerate(context_rows):
                    tensor = ContextTensor(
                        batch_values[index], batch_type_ids, batch_valid[index],
                        series_ids,
                    )
                    tensor.validate()
                    context_tensor_by_id[candidate["candidate_id"]] = tensor

            verified_cutoffs: dict[str, int] = {}
            session_source: SessionEventSource | None = None
            if candidate_rows:
                if pack is None:
                    raise C.EntryV2Refusal("candidate has no open event pack")
                prefix_expectations: list[tuple[int, str]] = []
                for candidate in candidate_rows:
                    candidate_id = candidate["candidate_id"]
                    decision = _int(candidate, "decision_ts_ns")
                    if _int(candidate, "locked_iid") != pack.header.locked_iid:
                        raise C.EntryV2Refusal(
                            "candidate locked IID differs from event pack"
                        )
                    cutoff = pack.cutoff(decision)
                    declared_cutoff = _int(candidate, "event_cutoff")
                    if cutoff != declared_cutoff or cutoff <= 0:
                        raise C.EntryV2Refusal(
                            "candidate lower_bound cutoff mismatch"
                        )
                    if (_int(candidate, "prefix_last_event_ordinal")
                            != cutoff - 1
                            or _int(
                                candidate,
                                "prefix_last_availability_ts_ns",
                            ) != int(pack.rows[cutoff - 1]["ts_recv_ns"])):
                        raise C.EntryV2Refusal(
                            "candidate prefix last event mismatch"
                        )
                    if candidate["event_pack_sha256"] != event_hash:
                        raise C.EntryV2Refusal(
                            "candidate row event-pack pin differs from manifest"
                        )
                    if candidate["clock_law_receipt_sha256"] != (
                            CLOCK_LAW_RECEIPT_FILE_SHA256):
                        raise C.EntryV2Refusal(
                            "candidate row clock-law file pin differs"
                        )
                    if int(pack.rows[cutoff - 1]["ts_recv_ns"]) >= decision:
                        raise C.EntryV2Refusal(
                            "candidate prefix reaches equal/future time"
                        )
                    verified_cutoffs[candidate_id] = cutoff
                    prefix_expectations.append(
                        (cutoff, candidate["prefix_sha256"])
                    )
                unique, bytes_hashed = verify_prefixes_once(
                    pack, prefix_expectations
                )
                prefix_unique_cutoffs += unique
                prefix_bytes_hashed += bytes_hashed
                maximum_candidate_cutoff = max(verified_cutoffs.values())
                pin = event_source_pins.get(session)
                if pin is None:
                    raise C.EntryV2Refusal(
                        "candidate session has no verified event-source pin"
                    )
                pin["max_cutoff"] = maximum_candidate_cutoff
                session_source = SessionEventSource(
                    array_cache=array_cache, **pin
                )
                if array_cache is not None:
                    if verified_hit:
                        if (durable_store is None or not durable_store.has_product(
                                "session-arrays",
                                session_source.durable_identity(),
                                MODEL_ARRAYS_CONVERSION_LAW_SHA256)):
                            raise C.EntryV2Refusal(
                                "verified-session array product is absent; rebuild forbidden"
                            )
                        with session_source.open_arrays():
                            pass
                    else:
                        session_source.publish_from_open_pack(pack)
                if diagnostic_observer is not None:
                    if verified_hit:
                        cached = getattr(
                            diagnostic_observer, "observe_cached_session", None
                        )
                        if cached is None:
                            raise C.EntryV2Refusal(
                                "diagnostic observer lacks verified-session reload"
                            )
                        cached(
                            source=session_source,
                            candidates=tuple(candidate_rows),
                            teachers=tuple(teacher_rows),
                        )
                    else:
                        diagnostic_observer.observe_session(
                            source=session_source,
                            pack=pack,
                            candidates=tuple(candidate_rows),
                            teachers=tuple(teacher_rows),
                        )

            for candidate in candidate_rows:
                candidate_id = candidate["candidate_id"]
                if not candidate_id or candidate_id in candidate_ids_seen:
                    raise C.EntryV2Refusal("duplicate/empty corpus candidate_id")
                candidate_ids_seen.add(candidate_id)
                teacher = teacher_by_id.get(candidate_id)
                if teacher is not None and (
                        teacher["asset"], _int(teacher, "d8")) != (asset, d8):
                    raise C.EntryV2Refusal("teacher row identity mismatch")
                if (candidate["asset"], _int(candidate, "d8")) != (asset, d8):
                    raise C.EntryV2Refusal("candidate row identity mismatch")
                decision = _int(candidate, "decision_ts_ns")
                compliance = candidate["compliance_status"]
                if compliance not in compliance_counts:
                    raise C.EntryV2Refusal("unknown candidate compliance status")
                if teacher is not None and teacher["compliance_status"] != compliance:
                    raise C.EntryV2Refusal("candidate/teacher compliance mismatch")
                compliance_counts[compliance] += 1
                if teacher is not None and _int(teacher, "decision_ts_ns") != decision:
                    raise C.EntryV2Refusal("teacher decision timestamp is permuted")
                if pack is None:
                    raise C.EntryV2Refusal("candidate has no open event pack")
                cutoff = verified_cutoffs[candidate_id]
                prefix_events += cutoff
                _sha(candidate["lineage_sha256"], "candidate lineage")

                if compliance != "CLEAR":
                    continue
                clear_expected += 1
                if teacher is None:
                    continue
                clear_joined += 1
                teacher_status = teacher["status"]
                if teacher_status == "NO_SANE_SUFFIX":
                    if (any(_int(teacher, name) != 0 for name in (
                            "exit_ts_ns", "wall_hit", "payer", "take_target"))
                            or any(float(_float(teacher, name)) != 0.0 for name in (
                                "cert_close_usd", "mfe_usd", "mae_usd",
                                "time_to_peak_sec"))):
                        raise C.EntryV2Refusal(
                            "typed NO_SANE_SUFFIX teacher carries target values"
                        )
                    clear_typed_no_sane_suffix += 1
                    continue
                if teacher_status != "READY":
                    raise C.EntryV2Refusal("teacher row has an unknown status")
                clear_ready += 1
                exit_ts = _int(teacher, "exit_ts_ns")
                cert = float(_float(teacher, "cert_close_usd"))
                mfe = float(_float(teacher, "mfe_usd"))
                mae = float(_float(teacher, "mae_usd"))
                time_peak = float(_float(teacher, "time_to_peak_sec"))
                wall = _bit(teacher, "wall_hit")
                if exit_ts < decision or _bit(teacher, "payer") != (cert > 0.0):
                    raise C.EntryV2Refusal("teacher exit/payer law mismatch")
                # The native row's candidate-local threshold bit is parsed
                # only as a schema bit.  It is not the training action: exact
                # ENTER/SKIP labels are rebuilt below from clean paths under
                # chronological occupancy and caps.
                _bit(teacher, "take_target")
                if wall != (cert <= -C.WALL_USD):
                    raise C.EntryV2Refusal("teacher wall status/value mismatch")

                query = ForecastQuery(
                    candidate_id, asset, d8, decision, _int(candidate, "phase"))
                forecast_features, forecast_hash = _forecast_features(provider, query)
                forecast_lineage.append(forecast_hash)
                features = _candidate_features(candidate, forecast_features)
                context_tensor = context_tensor_by_id[candidate_id]
                context = None
                if not audit_context_recorded and bool(context_tensor.valid.any()):
                    context = context_repo.pack(d8, decision)
                    reference = tensorize_context_pack(context)
                    if (not torch.equal(reference.values, context_tensor.values)
                            or not torch.equal(reference.type_ids,
                                               context_tensor.type_ids)
                            or not torch.equal(reference.valid,
                                               context_tensor.valid)):
                        raise C.EntryV2Refusal(
                            "batched context differs from causal reference"
                        )
                    audit_context_recorded = True
                context_content_hash = _tensor_hash(
                    context_tensor.values.detach().cpu().numpy(),
                    context_tensor.type_ids.detach().cpu().numpy(),
                    context_tensor.valid.detach().cpu().numpy())
                example_lineage = C.object_sha256({
                    "schema": "entry-v2-example-input-lineage-v2",
                    "candidate_lineage_sha256": candidate["lineage_sha256"],
                    "forecast_row_lineage_sha256": forecast_hash,
                    "context_receipt_sha256": context_receipts[asset],
                    "packed_context_sha256": context_content_hash,
                })
                side = Side.LONG if _int(candidate, "side") == 1 else Side.SHORT
                raw_ref = RawPrefixRef(
                    shard=str(pack.path), event_start_index=0,
                    event_end_index=cutoff, event_count=cutoff,
                    first_availability_ts_ns=int(pack.rows[0]["ts_recv_ns"]),
                    last_availability_ts_ns=int(
                        pack.rows[cutoff - 1]["ts_recv_ns"]
                    ),
                    source_hash=event_hash,
                )
                example = CausalEntryExample(
                    candidate_id=candidate_id, asset=asset, trading_day=d8,
                    session_id=session.session_id, decision_ts_ns=decision, side=side,
                    phase=f"G1_PHASE_{_int(candidate, 'phase')}",
                    locked_iid=_int(candidate, "locked_iid"), raw_prefix_ref=raw_ref,
                    causal_features=features, context=context,
                    lineage_hash=example_lineage,
                )
                if verified_hit:
                    try:
                        horizon_value, horizon_valid, phase_class, phase_valid = (
                            verified_targets[candidate_id]
                        )
                    except KeyError as exc:
                        raise C.EntryV2Refusal(
                            "verified-session target candidate differs"
                        ) from exc
                else:
                    horizon_value, horizon_valid, phase_class, phase_valid = (
                        _horizon_targets(pack, candidate))
                examples_by_session.setdefault(session, []).append(example)
                feature_by_id[candidate_id] = tuple(features[name]
                                                    for name in CANDIDATE_FEATURE_SCHEMA)
                target_by_id[candidate_id] = (
                    horizon_value, horizon_valid, phase_class, phase_valid)
                teacher_paths.append(TeacherPath(
                    candidate_id, asset, d8, decision, exit_ts, cert, mfe, mae,
                    wall, time_peak))
                outcomes[candidate_id] = ReplayOutcome(
                    candidate_id, exit_ts, cert, exit_ts, cert,
                    wall_hit_ts_ns=exit_ts if wall else None,
                    wall_pnl_usd=cert if wall else -C.WALL_USD,
                )
                # Retain this exact tensor for the later chronological stack;
                # rebuilding it would repeat the causal context search.
                context_tensor.validate()
            if not verified_hit and durable_store is not None:
                current_target_ids = tuple(
                    row["candidate_id"] for row in candidate_rows
                    if row["candidate_id"] in target_by_id
                )
                legacy_values = np.stack(
                    [target_by_id[candidate_id][0]
                     for candidate_id in current_target_ids]
                ) if current_target_ids else np.empty(
                    (0, len(HORIZONS_SECONDS)), np.float64)
                legacy_valid = np.stack(
                    [target_by_id[candidate_id][1]
                     for candidate_id in current_target_ids]
                ) if current_target_ids else np.empty(
                    (0, len(HORIZONS_SECONDS)), np.bool_)
                legacy_phase = np.asarray([
                    (int(target_by_id[candidate_id][2]),
                     int(target_by_id[candidate_id][3]))
                    for candidate_id in current_target_ids
                ], dtype=np.int64).reshape((-1, 2))
                prefix_rows = (
                    np.asarray(pack.rows[:max(verified_cutoffs.values())]).copy()
                    if pack is not None and verified_cutoffs
                    else np.empty((0,), dtype=EVENT_DTYPE)
                )
                source_pin_semantic: dict[str, Any] = {}
                if event_hash != "ABSENT":
                    source_pin_semantic = {
                        **event_source_pins[session],
                        "qre2_path": str(event_source_pins[session]["qre2_path"]),
                        "record_start_d8": int(pack.sidecar["record_window"][
                            "start_d8"]),
                        "record_end_d8_exclusive": int(pack.sidecar[
                            "record_window"]["end_d8_exclusive"]),
                    }
                measured = ({"physical_full_pack_opens": int(pack is not None),
                             "model_array_physical_fills": 0}
                            if session_source is None
                            else session_source.measurements.snapshot())
                published = durable_store.publish(
                    "verified-sessions", verified_identity,
                    VERIFIED_SESSION_LAW_SHA256,
                    tuple(np.frombuffer(raw, dtype=np.uint8).copy() for raw in (
                        candidate_raw, teacher_raw, candidate_receipt_raw,
                        teacher_receipt_raw,
                    )) + (prefix_rows.view(np.uint8), legacy_values,
                          legacy_valid, legacy_phase),
                    semantic={
                        "schema": "entry-v2-verified-session-map-v1",
                        "source_pin": source_pin_semantic,
                        "target_candidate_ids": list(current_target_ids),
                        "prefix_unique_cutoffs": len(set(verified_cutoffs.values())),
                    },
                    producer={
                        "schema": "entry-v2-verified-session-producer-v1",
                        "physical_full_pack_opens": int(
                            measured["physical_full_pack_opens"]),
                        "model_array_physical_fills": int(
                            measured["model_array_physical_fills"]),
                        "candidate_payload_reads": 1,
                        "teacher_payload_reads": 1,
                    },
                )
                published.close()
                verified_session_cold_publishes += 1
            if session_source is not None:
                model_array_bytes = SessionArrayCache.planned_bytes(session_source)
                source_measurements = session_source.measurements.snapshot()
                if verified_hit:
                    model_array_bytes_reused += model_array_bytes
                elif source_measurements["model_array_physical_fills"] == 1:
                    model_array_bytes_materialized += model_array_bytes
                model_array_physical_fills += int(
                    source_measurements["model_array_physical_fills"]
                )
            physical_full_pack_opens += int(
                not verified_hit and pack is not None
            )
            if pack is not None:
                pack.close()
            if verified_product is not None:
                verified_product.close()

        artifact_receipts.append({
            "asset": asset,
            "candidate_manifest_sha256": item.candidate_manifest_sha256,
            "teacher_manifest_sha256": item.teacher_manifest_sha256,
            "candidate_receipt_sha256": item.candidate_receipt_sha256,
            "teacher_receipt_sha256": item.teacher_receipt_sha256,
            "sessions": sum(
                _int(row, "d8") <= resolved_maximum_d8
                and (resolved_minimum_d8 is None
                     or _int(row, "d8") > resolved_minimum_d8)
                for row in candidate_manifest
            ),
            "full_manifest_sessions": len(candidate_manifest),
        })

    join_payload = {
        "schema": "entry-v2-teacher-join-v2",
        "expected_clear": clear_expected,
        "joined": clear_joined,
        "ready": clear_ready,
        "typed_no_sane_suffix": clear_typed_no_sane_suffix,
        "candidate_ids": sorted(example.candidate_id
                                for rows in examples_by_session.values()
                                for example in rows),
        "candidate_receipts": sorted(candidate_receipt_hashes),
        "teacher_receipts": sorted(teacher_receipt_hashes),
    }
    join_sha = C.object_sha256(join_payload)
    teacher_receipt_sha = C.object_sha256(sorted(teacher_receipt_hashes))
    teacher_evidence = TeacherAlignmentEvidence(
        expected_candidates=clear_expected,
        matched_candidates=clear_joined,
        mismatched_candidates=clear_expected - clear_joined,
        teacher_receipt_sha256=teacher_receipt_sha,
        join_receipt_sha256=join_sha,
    )
    teacher_evidence.validate()
    if not teacher_evidence.passed:
        raise TeacherAlignmentRefusal(
            f"CLEAR teacher identity join failed: {clear_joined}/{clear_expected}",
            teacher_evidence)
    if not teacher_paths:
        raise C.EntryV2Refusal("development corpus has no CLEAR READY candidates")

    raw_evidence = RawPrefixFidelityEvidence(
        expected_events=prefix_events,
        observed_events=prefix_events,
        mismatched_events=0,
        source_receipt_sha256=C.object_sha256(sorted(candidate_receipt_hashes)),
        pack_receipt_sha256=C.object_sha256(sorted(sidecar_hashes)),
    )
    raw_evidence.validate()

    sessions: list[EntrySessionSpec] = []
    session_receipts: list[dict[str, Any]] = []
    for session in sorted(
            examples_by_session,
            key=lambda item: (item.trading_day, item.asset, item.session_id)):
        examples = tuple(sorted(examples_by_session[session],
                                key=lambda item: (item.decision_ts_ns,
                                                  item.candidate_id)))
        context_items = [
            context_tensor_by_id.pop(example.candidate_id)
            for example in examples
        ]
        context_values, context_type_ids, context_valid = stack_context_tensors(context_items)
        feature_array = np.asarray(
            [feature_by_id[example.candidate_id] for example in examples],
            dtype=np.float64)
        horizon_value = np.stack(
            [target_by_id[example.candidate_id][0] for example in examples])
        horizon_valid = np.stack(
            [target_by_id[example.candidate_id][1] for example in examples])
        phase = np.asarray(
            [target_by_id[example.candidate_id][2] for example in examples],
            dtype=np.int64)
        phase_valid = np.asarray(
            [target_by_id[example.candidate_id][3] for example in examples],
            dtype=np.bool_)
        candidate_cutoffs = torch.tensor(
            [example.raw_prefix_ref.event_count for example in examples],
            dtype=torch.int64)
        pin = event_source_pins.get(session)
        if pin is None:
            raise C.EntryV2Refusal("candidate session has no verified event-source pin")
        current_stat = pin["qre2_path"].stat()
        current_identity = (
            current_stat.st_size, current_stat.st_dev, current_stat.st_ino,
            current_stat.st_mtime_ns, current_stat.st_ctime_ns)
        pinned_identity = (
            pin["source_size_bytes"], pin["source_device"], pin["source_inode"],
            pin["source_mtime_ns"], pin["source_ctime_ns"])
        if current_identity != pinned_identity:
            raise C.EntryV2Refusal("QRE2 source changed after corpus trust-boundary hash")
        if "max_cutoff" not in pin:
            raise C.EntryV2Refusal(
                "candidate session source lacks all-candidate cutoff"
            )
        source = SessionEventSource(array_cache=array_cache, **pin)
        spec = EntrySessionSpec(
            source=source,
            examples=examples,
            candidate_cutoffs=candidate_cutoffs,
            candidate_features=torch.from_numpy(feature_array),
            context_values=context_values,
            context_type_ids=context_type_ids,
            context_valid=context_valid,
            self_supervised=SelfSupervisedTargets(
                torch.from_numpy(horizon_value), torch.from_numpy(horizon_valid),
                torch.from_numpy(phase), torch.from_numpy(phase_valid)),
        )
        spec = replace(spec, static_features=torch.from_numpy(
            _static_context_summary(spec)
        ))
        spec.validate()
        sessions.append(spec)
        session_receipts.append({
            "asset": session.asset,
            "d8": session.trading_day,
            "session_id": session.session_id,
            "candidate_ids": list(spec.candidate_ids),
            "stream_receipt_sha256": source.receipt.receipt_sha256,
            "tensors_sha256": _tensor_hash(
                candidate_cutoffs.numpy(), feature_array,
                context_values.detach().cpu().numpy(),
                context_type_ids.detach().cpu().numpy(),
                context_valid.detach().cpu().numpy(), horizon_value,
                horizon_valid, phase, phase_valid),
        })

    if context_tensor_by_id:
        raise AssertionError("unconsumed candidate context tensors")

    regime_declarations: list[AssetDayRegime] = []
    for asset, d8 in sorted(expected_session_open_ns):
        snapshot = provider.session_regime(asset, d8)
        if snapshot is None:
            raise C.EntryV2Refusal("asset-day has no causal SESSION forecast row")
        open_ns = expected_session_open_ns[(asset, d8)]
        if (snapshot.segment != "SESSION"
                or int(snapshot.availability_ts_ns) != open_ns):
            raise C.EntryV2Refusal(
                "asset-day regime was not frozen at the actual session open"
            )
        regime = (
            snapshot.regime
            if snapshot.status == "READY"
            and snapshot.regime in {"LOW", "MID", "HIGH"}
            else "UNKNOWN"
        )
        regime_declarations.append(AssetDayRegime(
            asset, d8, regime, snapshot.availability_ts_ns
        ))

    teacher_store = build_teacher_store(
        teacher_paths, expected_sessions=expected_sessions
    )
    for spec in sessions:
        spec.validate(teacher_store)
    replay_data = ReplayCalibrationData(
        MappingProxyType(dict(sorted(outcomes.items()))),
        tuple(sorted(expected_sessions)),
        tuple(regime_declarations),
    )
    replay_data.validate(sessions)

    ordered_sources = [spec.source for spec in sorted(sessions, key=lambda item: (
        item.trading_day, item.asset, item.session_id))]
    stream_receipt_aggregate = C.object_sha256([
        source.receipt.receipt_sha256 for source in ordered_sources
    ])
    forecast_receipt_sha256 = _sha(
        getattr(provider, "receipt_sha256", ""), "forecast receipt")
    clock_law_receipt_sha256 = _clock_law_receipt_sha256()
    corpus_source_lineage_sha256 = C.object_sha256({
        "event_sources": [
            [source.asset, source.d8, source.source_sha256, source.sidecar_sha256]
            for source in ordered_sources
        ],
        "candidate_receipts": sorted(candidate_receipt_hashes),
        "teacher_receipts": sorted(teacher_receipt_hashes),
        "forecast_receipt": forecast_receipt_sha256,
        "context_receipts": dict(sorted(context_receipts.items())),
        "qre2_calendar_authority": C.QRE2_CALENDAR_SHA256,
        "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
        "maximum_d8": resolved_maximum_d8,
        "minimum_d8_exclusive": resolved_minimum_d8,
        "full_manifest_authorities": sorted(
            full_authorities, key=lambda row: str(row["asset"])),
    })

    receipt: dict[str, Any] = {
        "schema": CORPUS_SCHEMA,
        "holdout_start_d8": C.HOLDOUT_START_D8,
        "final_exam_permit": False,
        "corpus_window": {
            "schema": CORPUS_WINDOW_SCHEMA,
            "law_sha256": CORPUS_WINDOW_LAW_SHA256,
            "maximum_d8": resolved_maximum_d8,
            "minimum_d8_exclusive": resolved_minimum_d8,
            "start_d8_inclusive": min(observed_manifest_days),
            "observed_start_d8": min(observed_manifest_days),
            "observed_end_d8": max(observed_manifest_days),
            "full_manifest_authorities": sorted(
                full_authorities, key=lambda row: str(row["asset"])),
            "full_manifest_authority_sha256": C.object_sha256(sorted(
                full_authorities, key=lambda row: str(row["asset"]))),
        },
        "artifacts": artifact_receipts,
        "sessions": len(expected_sessions),
        "verified_session_warm_hits": verified_session_warm_hits,
        "verified_session_cold_publishes": verified_session_cold_publishes,
        "model_array_bytes_materialized": model_array_bytes_materialized,
        "model_array_bytes_reused": model_array_bytes_reused,
        "physical_full_pack_opens": physical_full_pack_opens,
        "model_array_physical_fills": model_array_physical_fills,
        "warm_corpus_ready": bool(
            durable_store is not None
            and verified_session_cold_publishes == 0
            and verified_session_warm_hits == len(observed_manifest_days)
        ),
        "denominator_calendar": {
            "law": (
                "QRE2CAL1 authenticated per-asset source coverage followed by "
                "asset-aware Monday-Friday trade dates; only authority-marked "
                "FULL_CLOSE rows excluded inside coverage; every other typed "
                "empty/refused/outage row retained at zero"
            ),
            "authority_sha256": C.QRE2_CALENDAR_SHA256,
            "asset_coverage_start_d8": {
                asset: C.qre2_asset_coverage_start_d8(asset)
                for asset in sorted(required)
            },
            "excluded_non_trading_calendar_rows": dict(sorted(
                excluded_non_trading_calendar_rows.items())),
            "excluded_outside_asset_coverage_rows": dict(sorted(
                excluded_outside_asset_coverage_rows.items())),
            "excluded_full_closure_rows": dict(sorted(
                excluded_full_closure_rows.items())),
        },
        "asset_day_regimes": {
            "law": (
                "QRE2 SESSION regime_tag frozen at session-open from strictly-"
                "prior data; WEAK=LOW; missing/NA is typed UNKNOWN"
            ),
            "resolved": len(regime_declarations),
            "expected": len({
                (session.asset, session.trading_day)
                for session in expected_sessions
            }),
            "declarations": [
                {
                    "asset": row.asset,
                    "trading_day": row.trading_day,
                    "regime": row.regime,
                    "availability_ts_ns": row.availability_ts_ns,
                }
                for row in regime_declarations
            ],
        },
        "candidate_batches": len(sessions),
        "clear_ready_candidates": len(teacher_paths),
        "clear_typed_no_sane_suffix": clear_typed_no_sane_suffix,
        "compliance_counts": compliance_counts,
        "candidate_feature_schema": list(CANDIDATE_FEATURE_SCHEMA),
        "candidate_feature_schema_sha256": C.object_sha256(
            list(CANDIDATE_FEATURE_SCHEMA)),
        "forecast_schema": FORECAST_SCHEMA,
        "forecast_feature_fields": list(FORECAST_FEATURE_FIELDS),
        "forecast_receipt_sha256": forecast_receipt_sha256,
        "test_forecast_adapter": _is_test_forecast_provider(provider),
        "used_forecast_lineage_sha256": C.object_sha256(sorted(forecast_lineage)),
        "context_receipts": dict(sorted(context_receipts.items())),
        "prefix_law": (
            "lower_bound(ts_recv_ns,decision_ts_ns); "
            "equal receive-time batch future"
        ),
        "prefix_domain_hex": PREFIX_DOMAIN.hex(),
        "prefix_verification": {
            "law": "one incremental pass per session over sorted unique cutoffs",
            "unique_cutoffs": prefix_unique_cutoffs,
            "bytes_hashed": prefix_bytes_hashed,
        },
        "self_supervised_horizon_law": (
            "first valid on-tick two-sided BBO at/after decision+h; "
            "side midpoint USD change minus frozen candidate cost; target-only mask"
        ),
        "self_supervised_phase_law": (
            "60s target-row bits: midpoint_up | spread_wider<<1 | "
            "bid_size_dominant<<2; target-only mask"
        ),
        "horizons_seconds": list(HORIZONS_SECONDS),
        "event_continuous_fields": list(CONTINUOUS_FIELDS),
        "event_categorical_fields": list(CATEGORICAL_FIELDS),
        "event_category_sizes": list(CATEGORY_SIZES),
        "model_arrays_conversion_law_sha256":
            MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        "session_stream_receipt_aggregate_sha256": stream_receipt_aggregate,
        "corpus_source_lineage_sha256": corpus_source_lineage_sha256,
        "clock_law_receipt_sha256": clock_law_receipt_sha256,
        "raw_prefix_fidelity": {
            "expected_events": raw_evidence.expected_events,
            "observed_events": raw_evidence.observed_events,
            "mismatched_events": raw_evidence.mismatched_events,
            "source_receipt_sha256": raw_evidence.source_receipt_sha256,
            "pack_receipt_sha256": raw_evidence.pack_receipt_sha256,
        },
        "teacher_alignment": {
            "expected_candidates": teacher_evidence.expected_candidates,
            "matched_candidates": teacher_evidence.matched_candidates,
            "mismatched_candidates": teacher_evidence.mismatched_candidates,
            "teacher_receipt_sha256": teacher_evidence.teacher_receipt_sha256,
            "join_receipt_sha256": teacher_evidence.join_receipt_sha256,
        },
        "teacher_store_sha256": teacher_store.store_hash,
        "teacher_action_contract": {
            "schema": "entry-v2-exact-oracle-teacher-v3",
            "denominator": "expected_asset_days",
            "expected_asset_days": len({
                (session.asset, session.trading_day)
                for session in expected_sessions
            }),
            "minimum_path_pnl_usd": C.MIN_EXPECTANCY_USD,
            "decision_law": (
                "chronological arrival-final; same-asset/same-timestamp highest "
                "cert_close_usd clearing $600, candidate_id tie-break"
            ),
            "blocked_action_rows": "action_loss_mask=false",
            "future_path_dp": "hindsight_ceiling_only",
            "occupancy": "one_open_position_per_asset",
            "max_entries_per_asset_day": C.MAX_ENTRIES_PER_ASSET_DAY,
            "max_entries_per_portfolio_day": C.MAX_ENTRIES_PORTFOLIO_DAY,
        },
        "session_specs": session_receipts,
    }
    receipt["receipt_sha256"] = C.object_sha256(receipt)
    model_input_binding = ModelInputBinding(
        tuple(CONTINUOUS_FIELDS),
        tuple(CATEGORICAL_FIELDS),
        tuple(CATEGORY_SIZES),
        MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        stream_receipt_aggregate,
        receipt["receipt_sha256"],
        corpus_source_lineage_sha256,
        clock_law_receipt_sha256,
    )
    model_input_binding.validate()
    return EntryCorpus(
        tuple(sessions), teacher_store, replay_data, raw_evidence,
        teacher_evidence, CANDIDATE_FEATURE_SCHEMA,
        MappingProxyType(receipt), model_input_binding,
        _CorpusMergeProvenance(
            tuple(sorted(candidate_ids_seen)),
            tuple(candidate_receipt_hashes),
            tuple(teacher_receipt_hashes),
            tuple(sidecar_hashes),
            tuple(forecast_lineage),
        ))


def merge_asset_corpora(
    corpora: Sequence[EntryCorpus],
    *,
    require_assets: Iterable[str] = C.ASSETS,
    maximum_d8: int | None = None,
    minimum_d8_exclusive: int | None = None,
) -> EntryCorpus:
    """Merge independently verified one-asset corpora without changing law.

    Asset lanes retain the unhashed receipt inputs needed to reproduce the
    canonical all-asset evidence and model binding.  Tensors and event sources
    are referenced directly; this function does not copy their storage.
    """

    resolved_maximum_d8 = (
        C.DEVELOPMENT_END_D8 if maximum_d8 is None else int(maximum_d8)
    )
    C.guard_date(resolved_maximum_d8)
    if resolved_maximum_d8 > C.DEVELOPMENT_END_D8:
        raise C.EntryV2Refusal("corpus maximum exceeds the development window")
    resolved_minimum_d8 = (
        None if minimum_d8_exclusive is None else int(minimum_d8_exclusive)
    )
    if resolved_minimum_d8 is not None:
        C.guard_date(resolved_minimum_d8)
        if resolved_minimum_d8 >= resolved_maximum_d8:
            raise C.EntryV2Refusal("corpus chronological interval is empty/reversed")
    required = {str(asset).upper() for asset in require_assets}
    if not required or not required.issubset(C.ASSETS):
        raise C.EntryV2Refusal("invalid required asset set for corpus merge")
    by_asset: dict[str, EntryCorpus] = {}
    for corpus in corpora:
        corpus.raw_prefix_fidelity.validate()
        corpus.teacher_alignment.validate()
        corpus.model_input_binding.validate()
        receipt = dict(corpus.receipt)
        claimed = receipt.pop("receipt_sha256", None)
        if (not isinstance(claimed, str)
                or C.object_sha256(receipt) != claimed
                or corpus.model_input_binding.corpus_receipt_sha256 != claimed):
            raise C.EntryV2Refusal("asset corpus receipt/model binding mismatch")
        if receipt.get("event_category_sizes") != list(
                corpus.model_input_binding.event_category_sizes):
            raise C.EntryV2Refusal(
                "asset corpus receipt category sizes differ from model binding"
            )
        assets = {session.asset for session in corpus.replay.expected_sessions}
        assets.update(spec.asset for spec in corpus.sessions)
        if len(assets) != 1:
            raise C.EntryV2Refusal("each merge input must contain exactly one asset")
        asset = next(iter(assets))
        if asset in by_asset:
            raise C.EntryV2Refusal(f"duplicate asset corpus: {asset}")
        if (tuple(corpus.teacher.expected_sessions)
                != tuple(corpus.replay.expected_sessions)):
            raise C.EntryV2Refusal("teacher/replay denominator differs in asset lane")
        by_asset[asset] = corpus
    if set(by_asset) != required:
        raise C.EntryV2Refusal(
            f"corpus merge assets must be exactly {sorted(required)}"
        )
    parts = tuple(by_asset[asset] for asset in sorted(required))

    # Constants and the full forecast-provider identity must be identical in
    # every lane.  In production this is guaranteed by
    # AssetScopedForecastProvider over one immutable all-asset provider.
    constant_keys = (
        "schema", "holdout_start_d8", "final_exam_permit",
        "candidate_feature_schema", "candidate_feature_schema_sha256",
        "forecast_schema", "forecast_feature_fields",
        "forecast_receipt_sha256", "test_forecast_adapter",
        "prefix_law", "prefix_domain_hex", "self_supervised_horizon_law",
        "self_supervised_phase_law", "horizons_seconds",
        "event_continuous_fields", "event_categorical_fields",
        "event_category_sizes",
        "model_arrays_conversion_law_sha256", "clock_law_receipt_sha256",
    )
    reference = parts[0].receipt
    reference_window = reference.get("corpus_window", {})
    if (reference_window.get("schema") != CORPUS_WINDOW_SCHEMA
            or reference_window.get("law_sha256") != CORPUS_WINDOW_LAW_SHA256
            or reference_window.get("maximum_d8") != resolved_maximum_d8
            or reference_window.get("minimum_d8_exclusive")
                != resolved_minimum_d8):
        raise C.EntryV2Refusal("asset corpus window identity is wrong")
    for part in parts[1:]:
        for key in constant_keys:
            if part.receipt.get(key) != reference.get(key):
                raise C.EntryV2Refusal(
                    f"asset corpus constant differs during merge: {key}"
                )
        window = part.receipt.get("corpus_window", {})
        if (window.get("schema"), window.get("law_sha256"),
                window.get("maximum_d8"),
                window.get("minimum_d8_exclusive")) != (
                    CORPUS_WINDOW_SCHEMA, CORPUS_WINDOW_LAW_SHA256,
                    resolved_maximum_d8, resolved_minimum_d8):
            raise C.EntryV2Refusal("asset corpora use different corpus windows")
        if (part.receipt.get("denominator_calendar", {}).get("authority_sha256")
                != reference.get("denominator_calendar", {}).get(
                    "authority_sha256")):
            raise C.EntryV2Refusal("asset corpora use different calendar authority")
        if (part.receipt.get("asset_day_regimes", {}).get("law")
                != reference.get("asset_day_regimes", {}).get("law")):
            raise C.EntryV2Refusal("asset corpora use different regime law")

    candidate_ids_seen: set[str] = set()
    candidate_receipt_hashes: list[str] = []
    teacher_receipt_hashes: list[str] = []
    sidecar_hashes: list[str] = []
    forecast_lineage: list[str] = []
    expected_sessions: list[SessionRef] = []
    regime_declarations: list[AssetDayRegime] = []
    outcomes: dict[str, ReplayOutcome] = {}
    sessions: list[EntrySessionSpec] = []
    teacher_paths: list[TeacherPath] = []
    audit_context_retained = False

    for part in parts:
        provenance = part._merge_provenance
        overlap = candidate_ids_seen.intersection(provenance.candidate_ids_seen)
        if overlap:
            raise C.EntryV2Refusal(
                f"cross-asset candidate id collision: {min(overlap)}"
            )
        candidate_ids_seen.update(provenance.candidate_ids_seen)
        candidate_receipt_hashes.extend(provenance.candidate_receipt_hashes)
        teacher_receipt_hashes.extend(provenance.teacher_receipt_hashes)
        sidecar_hashes.extend(provenance.sidecar_hashes)
        forecast_lineage.extend(provenance.forecast_lineage)
        expected_sessions.extend(part.replay.expected_sessions)
        regime_declarations.extend(part.replay.regime_declarations)
        for candidate_id, outcome in part.replay.outcomes.items():
            if candidate_id in outcomes:
                raise C.EntryV2Refusal(
                    f"cross-asset replay outcome collision: {candidate_id}"
                )
            outcomes[candidate_id] = outcome

        for spec in part.sessions:
            merged_examples: list[CausalEntryExample] = []
            changed = False
            for example in spec.examples:
                candidate_id = example.candidate_id
                label = part.teacher[candidate_id]
                outcome = part.replay.outcomes.get(candidate_id)
                if outcome is None or outcome.candidate_id != candidate_id:
                    raise C.EntryV2Refusal(
                        f"asset corpus outcome is missing: {candidate_id}"
                    )
                teacher_paths.append(TeacherPath(
                    candidate_id=candidate_id,
                    asset=example.asset,
                    trading_day=example.trading_day,
                    decision_ts_ns=example.decision_ts_ns,
                    exit_ts_ns=outcome.close_ts_ns,
                    cert_close_usd=label.cert_close_usd,
                    mfe_usd=label.mfe_usd,
                    mae_usd=label.mae_usd,
                    wall_hit=label.wall_hit,
                    time_to_peak_sec=label.time_to_peak_sec,
                ))
                if example.context is not None:
                    if audit_context_retained:
                        example = replace(example, context=None)
                        changed = True
                    else:
                        audit_context_retained = True
                merged_examples.append(example)
            sessions.append(
                replace(spec, examples=tuple(merged_examples)) if changed else spec
            )

    if len(expected_sessions) != len(set(expected_sessions)):
        raise C.EntryV2Refusal("asset corpus denominators overlap")
    regime_keys = {(row.asset, row.trading_day) for row in regime_declarations}
    if len(regime_keys) != len(regime_declarations):
        raise C.EntryV2Refusal("asset corpus regime declarations overlap")
    sessions.sort(key=lambda item: (item.trading_day, item.asset, item.session_id))
    expected_sessions.sort()
    regime_declarations.sort()

    teacher_store = build_teacher_store(
        teacher_paths, expected_sessions=expected_sessions
    )
    # Rebuilding globally is intentional: it proves ranks and occupancy actions
    # remain identical to the independently verified lanes.
    for part in parts:
        for spec in part.sessions:
            for candidate_id in spec.candidate_ids:
                if teacher_store[candidate_id] != part.teacher[candidate_id]:
                    raise C.EntryV2Refusal(
                        f"global teacher differs from asset lane: {candidate_id}"
                    )
    for spec in sessions:
        spec.validate(teacher_store)
    replay_data = ReplayCalibrationData(
        MappingProxyType(dict(sorted(outcomes.items()))),
        tuple(expected_sessions),
        tuple(regime_declarations),
    )
    replay_data.validate(sessions)

    clear_expected = sum(
        part.teacher_alignment.expected_candidates for part in parts
    )
    clear_joined = sum(
        part.teacher_alignment.matched_candidates for part in parts
    )
    clear_typed_no_sane_suffix = sum(
        int(part.receipt.get("clear_typed_no_sane_suffix", -1)) for part in parts
    )
    if clear_typed_no_sane_suffix < 0:
        raise C.EntryV2Refusal("asset corpus typed-teacher count is invalid")
    join_payload = {
        "schema": "entry-v2-teacher-join-v2",
        "expected_clear": clear_expected,
        "joined": clear_joined,
        "ready": len(teacher_paths),
        "typed_no_sane_suffix": clear_typed_no_sane_suffix,
        "candidate_ids": sorted(
            example.candidate_id for spec in sessions for example in spec.examples
        ),
        "candidate_receipts": sorted(candidate_receipt_hashes),
        "teacher_receipts": sorted(teacher_receipt_hashes),
    }
    teacher_evidence = TeacherAlignmentEvidence(
        expected_candidates=clear_expected,
        matched_candidates=clear_joined,
        mismatched_candidates=clear_expected - clear_joined,
        teacher_receipt_sha256=C.object_sha256(sorted(teacher_receipt_hashes)),
        join_receipt_sha256=C.object_sha256(join_payload),
    )
    teacher_evidence.validate()
    if not teacher_evidence.passed:
        raise TeacherAlignmentRefusal(
            "merged CLEAR teacher identity join failed", teacher_evidence
        )

    prefix_events = sum(part.raw_prefix_fidelity.expected_events for part in parts)
    raw_evidence = RawPrefixFidelityEvidence(
        expected_events=prefix_events,
        observed_events=sum(
            part.raw_prefix_fidelity.observed_events for part in parts
        ),
        mismatched_events=sum(
            part.raw_prefix_fidelity.mismatched_events for part in parts
        ),
        source_receipt_sha256=C.object_sha256(sorted(candidate_receipt_hashes)),
        pack_receipt_sha256=C.object_sha256(sorted(sidecar_hashes)),
    )
    raw_evidence.validate()

    ordered_sources = [
        spec.source for spec in sorted(
            sessions, key=lambda item: (
                item.trading_day, item.asset, item.session_id
            )
        )
    ]
    stream_receipt_aggregate = C.object_sha256([
        source.receipt.receipt_sha256 for source in ordered_sources
    ])
    context_receipts: dict[str, str] = {}
    artifact_receipts: list[Mapping[str, Any]] = []
    session_receipts: list[Mapping[str, Any]] = []
    compliance_counts = {
        "CLEAR": 0, "PROHIBITED": 0, "COMPLIANCE_UNKNOWN": 0
    }
    excluded_non_trading = {asset: 0 for asset in required}
    excluded_outside_coverage = {asset: 0 for asset in required}
    excluded_full_closure = {asset: 0 for asset in required}
    prefix_unique_cutoffs = 0
    prefix_bytes_hashed = 0
    for part in parts:
        context_receipts.update(part.receipt["context_receipts"])
        artifact_receipts.extend(part.receipt["artifacts"])
        session_receipts.extend(part.receipt["session_specs"])
        for name in compliance_counts:
            compliance_counts[name] += int(part.receipt["compliance_counts"][name])
        calendar = part.receipt["denominator_calendar"]
        for asset, value in calendar[
                "excluded_non_trading_calendar_rows"].items():
            excluded_non_trading[asset] += int(value)
        for asset, value in calendar[
                "excluded_outside_asset_coverage_rows"].items():
            excluded_outside_coverage[asset] += int(value)
        for asset, value in calendar["excluded_full_closure_rows"].items():
            excluded_full_closure[asset] += int(value)
        prefix_unique_cutoffs += int(
            part.receipt["prefix_verification"]["unique_cutoffs"]
        )
        prefix_bytes_hashed += int(
            part.receipt["prefix_verification"]["bytes_hashed"]
        )

    artifact_receipts.sort(key=lambda row: str(row["asset"]))
    session_receipts.sort(key=lambda row: (
        int(row["d8"]), str(row["asset"]), str(row["session_id"])
    ))
    forecast_receipt_sha256 = str(reference["forecast_receipt_sha256"])
    clock_law_receipt_sha256 = str(reference["clock_law_receipt_sha256"])
    corpus_source_lineage_sha256 = C.object_sha256({
        "event_sources": [
            [source.asset, source.d8, source.source_sha256, source.sidecar_sha256]
            for source in ordered_sources
        ],
        "candidate_receipts": sorted(candidate_receipt_hashes),
        "teacher_receipts": sorted(teacher_receipt_hashes),
        "forecast_receipt": forecast_receipt_sha256,
        "context_receipts": dict(sorted(context_receipts.items())),
        "qre2_calendar_authority": C.QRE2_CALENDAR_SHA256,
        "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
        "maximum_d8": resolved_maximum_d8,
        "minimum_d8_exclusive": resolved_minimum_d8,
        "full_manifest_authorities": sorted(
            (authority
             for part in parts
             for authority in part.receipt["corpus_window"][
                 "full_manifest_authorities"]),
            key=lambda row: str(row["asset"]),
        ),
    })

    receipt = dict(reference)
    receipt.pop("receipt_sha256", None)
    receipt.update({
        "artifacts": artifact_receipts,
        "sessions": len(expected_sessions),
        "verified_session_warm_hits": sum(int(
            part.receipt["verified_session_warm_hits"]) for part in parts),
        "verified_session_cold_publishes": sum(int(
            part.receipt["verified_session_cold_publishes"]) for part in parts),
        "model_array_bytes_materialized": sum(int(
            part.receipt["model_array_bytes_materialized"]) for part in parts),
        "model_array_bytes_reused": sum(int(
            part.receipt["model_array_bytes_reused"]) for part in parts),
        "physical_full_pack_opens": sum(int(
            part.receipt["physical_full_pack_opens"]) for part in parts),
        "model_array_physical_fills": sum(int(
            part.receipt["model_array_physical_fills"]) for part in parts),
        "warm_corpus_ready": all(
            part.receipt["warm_corpus_ready"] is True for part in parts),
        "corpus_window": {
            "schema": CORPUS_WINDOW_SCHEMA,
            "law_sha256": CORPUS_WINDOW_LAW_SHA256,
            "maximum_d8": resolved_maximum_d8,
            "minimum_d8_exclusive": resolved_minimum_d8,
            "start_d8_inclusive": min(int(
                part.receipt["corpus_window"]["start_d8_inclusive"]
            ) for part in parts),
            "observed_start_d8": min(int(
                part.receipt["corpus_window"]["observed_start_d8"]
            ) for part in parts),
            "observed_end_d8": max(int(
                part.receipt["corpus_window"]["observed_end_d8"]
            ) for part in parts),
            "full_manifest_authorities": sorted(
                (authority
                 for part in parts
                 for authority in part.receipt["corpus_window"][
                     "full_manifest_authorities"]),
                key=lambda row: str(row["asset"]),
            ),
            "full_manifest_authority_sha256": C.object_sha256(sorted(
                (authority
                 for part in parts
                 for authority in part.receipt["corpus_window"][
                     "full_manifest_authorities"]),
                key=lambda row: str(row["asset"]),
            )),
        },
        "denominator_calendar": {
            "law": reference["denominator_calendar"]["law"],
            "authority_sha256": C.QRE2_CALENDAR_SHA256,
            "asset_coverage_start_d8": {
                asset: C.qre2_asset_coverage_start_d8(asset)
                for asset in sorted(required)
            },
            "excluded_non_trading_calendar_rows": dict(sorted(
                excluded_non_trading.items()
            )),
            "excluded_outside_asset_coverage_rows": dict(sorted(
                excluded_outside_coverage.items()
            )),
            "excluded_full_closure_rows": dict(sorted(
                excluded_full_closure.items()
            )),
        },
        "asset_day_regimes": {
            "law": reference["asset_day_regimes"]["law"],
            "resolved": len(regime_declarations),
            "expected": len({
                (session.asset, session.trading_day)
                for session in expected_sessions
            }),
            "declarations": [
                {
                    "asset": row.asset,
                    "trading_day": row.trading_day,
                    "regime": row.regime,
                    "availability_ts_ns": row.availability_ts_ns,
                }
                for row in regime_declarations
            ],
        },
        "candidate_batches": len(sessions),
        "clear_ready_candidates": len(teacher_paths),
        "clear_typed_no_sane_suffix": clear_typed_no_sane_suffix,
        "compliance_counts": compliance_counts,
        "used_forecast_lineage_sha256": C.object_sha256(
            sorted(forecast_lineage)
        ),
        "context_receipts": dict(sorted(context_receipts.items())),
        "prefix_verification": {
            "law": reference["prefix_verification"]["law"],
            "unique_cutoffs": prefix_unique_cutoffs,
            "bytes_hashed": prefix_bytes_hashed,
        },
        "session_stream_receipt_aggregate_sha256": stream_receipt_aggregate,
        "corpus_source_lineage_sha256": corpus_source_lineage_sha256,
        "raw_prefix_fidelity": {
            "expected_events": raw_evidence.expected_events,
            "observed_events": raw_evidence.observed_events,
            "mismatched_events": raw_evidence.mismatched_events,
            "source_receipt_sha256": raw_evidence.source_receipt_sha256,
            "pack_receipt_sha256": raw_evidence.pack_receipt_sha256,
        },
        "teacher_alignment": {
            "expected_candidates": teacher_evidence.expected_candidates,
            "matched_candidates": teacher_evidence.matched_candidates,
            "mismatched_candidates": teacher_evidence.mismatched_candidates,
            "teacher_receipt_sha256": teacher_evidence.teacher_receipt_sha256,
            "join_receipt_sha256": teacher_evidence.join_receipt_sha256,
        },
        "teacher_store_sha256": teacher_store.store_hash,
        "teacher_action_contract": {
            **reference["teacher_action_contract"],
            "expected_asset_days": len({
                (session.asset, session.trading_day)
                for session in expected_sessions
            }),
        },
        "session_specs": session_receipts,
    })
    receipt["receipt_sha256"] = C.object_sha256(receipt)
    model_input_binding = ModelInputBinding(
        tuple(CONTINUOUS_FIELDS),
        tuple(CATEGORICAL_FIELDS),
        tuple(CATEGORY_SIZES),
        MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        stream_receipt_aggregate,
        receipt["receipt_sha256"],
        corpus_source_lineage_sha256,
        clock_law_receipt_sha256,
    )
    model_input_binding.validate()
    return EntryCorpus(
        tuple(sessions), teacher_store, replay_data, raw_evidence,
        teacher_evidence, CANDIDATE_FEATURE_SCHEMA,
        MappingProxyType(receipt), model_input_binding,
        _CorpusMergeProvenance(
            tuple(sorted(candidate_ids_seen)),
            tuple(candidate_receipt_hashes),
            tuple(teacher_receipt_hashes),
            tuple(sidecar_hashes),
            tuple(forecast_lineage),
        ),
    )


def merge_chronological_corpora(
    corpora: Sequence[EntryCorpus],
) -> EntryCorpus:
    """Merge adjacent all-asset intervals without reopening or copying payloads."""
    parts = tuple(corpora)
    if len(parts) < 2:
        raise C.EntryV2Refusal("chronological corpus merge requires multiple windows")
    constant_keys = (
        "schema", "holdout_start_d8", "final_exam_permit",
        "candidate_feature_schema", "candidate_feature_schema_sha256",
        "forecast_schema", "forecast_feature_fields", "forecast_receipt_sha256",
        "test_forecast_adapter", "prefix_law", "prefix_domain_hex",
        "self_supervised_horizon_law", "self_supervised_phase_law",
        "horizons_seconds", "selected_horizon_coordinates",
        "selected_horizon_schema_sha256", "selected_horizon_target_law",
        "selected_horizon_status_codes",
        "selected_horizon_coverage_schema",
        "selected_horizon_coverage_law",
        "selected_horizon_coverage_law_sha256",
        "selected_horizon_start_d8",
        "event_continuous_fields",
        "event_categorical_fields", "event_category_sizes",
        "model_arrays_conversion_law_sha256", "clock_law_receipt_sha256",
    )
    reference = parts[0].receipt
    reference_authorities = reference.get("corpus_window", {}).get(
        "full_manifest_authorities")
    reference_authority_hash = reference.get("corpus_window", {}).get(
        "full_manifest_authority_sha256")
    prior_maximum: int | None = None
    chain_parts: list[dict[str, Any]] = []
    for index, part in enumerate(parts):
        part.raw_prefix_fidelity.validate()
        part.teacher_alignment.validate()
        part.model_input_binding.validate()
        body = dict(part.receipt)
        claimed = body.pop("receipt_sha256", None)
        if (not isinstance(claimed, str) or C.object_sha256(body) != claimed
                or part.model_input_binding.corpus_receipt_sha256 != claimed):
            raise C.EntryV2Refusal("chronological corpus receipt binding drift")
        for key in constant_keys:
            if part.receipt.get(key) != reference.get(key):
                raise C.EntryV2Refusal(
                    f"chronological corpus constant differs: {key}"
                )
        window = part.receipt.get("corpus_window", {})
        minimum = window.get("minimum_d8_exclusive")
        maximum = int(window.get("maximum_d8", 0))
        if (window.get("schema") != CORPUS_WINDOW_SCHEMA
                or window.get("law_sha256") != CORPUS_WINDOW_LAW_SHA256
                or window.get("full_manifest_authorities") != reference_authorities
                or window.get("full_manifest_authority_sha256")
                    != reference_authority_hash):
            raise C.EntryV2Refusal(
                "chronological corpus authority/window law differs"
            )
        if index and minimum != prior_maximum:
            raise C.EntryV2Refusal("chronological corpus windows overlap or gap")
        if index == 0 and minimum is not None:
            # A chain may begin later than source history, but it must declare
            # that predecessor explicitly and remains the merged predecessor.
            C.guard_date(int(minimum))
        if maximum <= (int(minimum) if minimum is not None else 0):
            raise C.EntryV2Refusal("chronological corpus window is empty/reversed")
        if {session.asset for session in part.replay.expected_sessions} != set(C.ASSETS):
            raise C.EntryV2Refusal("chronological corpus window is not all-asset")
        prior_maximum = maximum
        chain_parts.append({
            "receipt_sha256": claimed,
            "minimum_d8_exclusive": minimum,
            "start_d8_inclusive": int(window["start_d8_inclusive"]),
            "maximum_d8": maximum,
        })

    candidate_ids: set[str] = set()
    candidate_receipts: list[str] = []
    teacher_receipts: list[str] = []
    sidecar_hashes: list[str] = []
    forecast_lineage: list[str] = []
    expected_sessions: list[SessionRef] = []
    regimes: list[AssetDayRegime] = []
    outcomes: dict[str, ReplayOutcome] = {}
    sessions: list[EntrySessionSpec] = []
    teacher_paths: list[TeacherPath] = []
    audit_context_retained = False
    for part in parts:
        provenance = part._merge_provenance
        overlap = candidate_ids.intersection(provenance.candidate_ids_seen)
        if overlap:
            raise C.EntryV2Refusal(
                f"chronological candidate overlap: {min(overlap)}"
            )
        candidate_ids.update(provenance.candidate_ids_seen)
        candidate_receipts.extend(provenance.candidate_receipt_hashes)
        teacher_receipts.extend(provenance.teacher_receipt_hashes)
        sidecar_hashes.extend(provenance.sidecar_hashes)
        forecast_lineage.extend(provenance.forecast_lineage)
        expected_sessions.extend(part.replay.expected_sessions)
        regimes.extend(part.replay.regime_declarations)
        for candidate_id, outcome in part.replay.outcomes.items():
            if candidate_id in outcomes:
                raise C.EntryV2Refusal(
                    f"chronological replay overlap: {candidate_id}"
                )
            outcomes[candidate_id] = outcome
        for spec in part.sessions:
            examples: list[CausalEntryExample] = []
            changed = False
            for example in spec.examples:
                label = part.teacher[example.candidate_id]
                outcome = part.replay.outcomes[example.candidate_id]
                teacher_paths.append(TeacherPath(
                    example.candidate_id, example.asset, example.trading_day,
                    example.decision_ts_ns, outcome.close_ts_ns,
                    label.cert_close_usd, label.mfe_usd, label.mae_usd,
                    label.wall_hit, label.time_to_peak_sec,
                ))
                if example.context is not None:
                    if audit_context_retained:
                        example = replace(example, context=None)
                        changed = True
                    else:
                        audit_context_retained = True
                examples.append(example)
            sessions.append(replace(spec, examples=tuple(examples)) if changed else spec)
    if len(expected_sessions) != len(set(expected_sessions)):
        raise C.EntryV2Refusal("chronological corpus denominator overlap")
    if len(regimes) != len({(row.asset, row.trading_day) for row in regimes}):
        raise C.EntryV2Refusal("chronological corpus regime overlap")
    sessions.sort(key=lambda item: (item.trading_day, item.asset, item.session_id))
    expected_sessions.sort()
    regimes.sort()
    teacher_store = build_teacher_store(
        teacher_paths, expected_sessions=expected_sessions
    )
    for part in parts:
        for spec in part.sessions:
            for candidate_id in spec.candidate_ids:
                if teacher_store[candidate_id] != part.teacher[candidate_id]:
                    raise C.EntryV2Refusal(
                        "chronological teacher semantics changed at window merge"
                    )
    for spec in sessions:
        spec.validate(teacher_store)
    replay = ReplayCalibrationData(
        MappingProxyType(dict(sorted(outcomes.items()))),
        tuple(expected_sessions), tuple(regimes),
    )
    replay.validate(sessions)

    clear_expected = sum(row.teacher_alignment.expected_candidates for row in parts)
    clear_joined = sum(row.teacher_alignment.matched_candidates for row in parts)
    typed_no_suffix = sum(int(row.receipt["clear_typed_no_sane_suffix"])
                          for row in parts)
    join_payload = {
        "schema": "entry-v2-teacher-join-v2",
        "expected_clear": clear_expected,
        "joined": clear_joined,
        "ready": len(teacher_paths),
        "typed_no_sane_suffix": typed_no_suffix,
        "candidate_ids": sorted(
            example.candidate_id for spec in sessions for example in spec.examples
        ),
        "candidate_receipts": sorted(candidate_receipts),
        "teacher_receipts": sorted(teacher_receipts),
    }
    teacher_evidence = TeacherAlignmentEvidence(
        clear_expected, clear_joined, clear_expected - clear_joined,
        C.object_sha256(sorted(teacher_receipts)), C.object_sha256(join_payload),
    )
    teacher_evidence.validate()
    if not teacher_evidence.passed:
        raise TeacherAlignmentRefusal(
            "chronological teacher identity join failed", teacher_evidence
        )
    raw_evidence = RawPrefixFidelityEvidence(
        sum(row.raw_prefix_fidelity.expected_events for row in parts),
        sum(row.raw_prefix_fidelity.observed_events for row in parts),
        sum(row.raw_prefix_fidelity.mismatched_events for row in parts),
        C.object_sha256(sorted(candidate_receipts)),
        C.object_sha256(sorted(sidecar_hashes)),
    )
    raw_evidence.validate()

    ordered_sources = [spec.source for spec in sessions]
    stream_hash = C.object_sha256([
        source.receipt.receipt_sha256 for source in ordered_sources
    ])
    context_receipts = dict(reference["context_receipts"])
    for part in parts[1:]:
        if part.receipt["context_receipts"] != context_receipts:
            raise C.EntryV2Refusal("chronological context authority differs")
    artifacts_by_asset: dict[str, dict[str, Any]] = {}
    for part in parts:
        for artifact in part.receipt["artifacts"]:
            asset = str(artifact["asset"])
            row = dict(artifact)
            prior = artifacts_by_asset.get(asset)
            if prior is None:
                artifacts_by_asset[asset] = row
            else:
                for key, value in row.items():
                    if key == "sessions":
                        continue
                    if prior.get(key) != value:
                        raise C.EntryV2Refusal(
                            "chronological artifact authority differs"
                        )
                prior["sessions"] = int(prior["sessions"]) + int(row["sessions"])
    session_receipts = sorted(
        (receipt for part in parts for receipt in part.receipt["session_specs"]),
        key=lambda row: (int(row["d8"]), str(row["asset"]), str(row["session_id"])),
    )
    receipt_by_key = {
        (str(row["asset"]), int(row["d8"]), str(row["session_id"])): row
        for row in session_receipts
    }
    if len(receipt_by_key) != len(session_receipts):
        raise C.EntryV2Refusal(
            "chronological selected-horizon receipt roster duplicates a session"
        )
    selected_horizon_hashes = tuple(
        row.get("selected_horizon_tensors_sha256") for row in session_receipts
    )
    coverage_values = tuple(
        part.receipt.get("selected_horizon_coverage") for part in parts
    )
    has_coverage = any(value is not None for value in coverage_values)
    merged_coverage: Mapping[str, object] | None = None
    if has_coverage:
        if not all(isinstance(value, Mapping) for value in coverage_values):
            raise C.EntryV2Refusal(
                "chronological selected-horizon coverage is partially bound"
            )
        diagnostic_roster: list[Mapping[str, Any]] = []
        try:
            for part, value in zip(parts, coverage_values):
                assert isinstance(value, Mapping)
                validate_selected_horizon_coverage(value)
                if (part.receipt.get("selected_horizon_coverage_schema")
                        != SELECTED_HORIZON_COVERAGE_SCHEMA
                        or part.receipt.get("selected_horizon_coverage_law")
                            != SELECTED_HORIZON_COVERAGE_LAW
                        or part.receipt.get(
                            "selected_horizon_coverage_law_sha256")
                            != SELECTED_HORIZON_COVERAGE_LAW_SHA256
                        or part.receipt.get("selected_horizon_start_d8")
                            != reference.get("selected_horizon_start_d8")
                        or part.receipt.get("selected_horizon_coverage_sha256")
                            != value.get("receipt_sha256")):
                    raise C.EntryV2Refusal(
                        "chronological selected-horizon coverage binding differs"
                    )
                diagnostic_roster.extend(value["diagnostic_sessions"])

            actual_corpus_roster: list[dict[str, object]] = []
            for spec in sessions:
                selected = (
                    spec.selected_horizon_value, spec.selected_horizon_valid,
                    spec.selected_horizon_schema_sha256,
                )
                if any(value is not None for value in selected) and any(
                        value is None for value in selected):
                    raise C.EntryV2Refusal(
                        "chronological selected-horizon carrier is incomplete"
                    )
                attached = all(value is not None for value in selected)
                receipt_row = receipt_by_key.get(
                    (spec.asset, spec.trading_day, spec.session_id))
                receipt_hash = None if receipt_row is None else receipt_row.get(
                    "selected_horizon_tensors_sha256")
                if receipt_row is None or attached != isinstance(receipt_hash, str):
                    raise C.EntryV2Refusal(
                        "chronological selected-horizon carrier/receipt differs"
                    )
                actual_corpus_roster.append({
                    "asset": spec.asset,
                    "trading_day": spec.trading_day,
                    "session_id": spec.session_id,
                    "candidate_count": len(spec.candidate_ids),
                    "candidate_ids_sha256": C.object_sha256(
                        list(spec.candidate_ids)),
                    "selected_attached": attached,
                })
            merged_coverage = selected_horizon_coverage_receipt(
                start_d8=int(reference["selected_horizon_start_d8"]),
                corpus_sessions=actual_corpus_roster,
                diagnostic_sessions=diagnostic_roster,
            )
        except SelectedHorizonContractRefusal as exc:
            raise C.EntryV2Refusal(
                "chronological selected-horizon coverage is not exact"
            ) from exc
    elif (any(value is not None for value in selected_horizon_hashes)
          or any(any(value is not None for value in (
              spec.selected_horizon_value, spec.selected_horizon_valid,
              spec.selected_horizon_schema_sha256)) for spec in sessions)):
        raise C.EntryV2Refusal(
            "chronological selected-horizon targets lack coverage authority"
        )
    compliance = {name: sum(int(part.receipt["compliance_counts"][name])
                            for part in parts)
                  for name in ("CLEAR", "PROHIBITED", "COMPLIANCE_UNKNOWN")}
    excluded = {}
    for name in ("excluded_non_trading_calendar_rows",
                 "excluded_outside_asset_coverage_rows",
                 "excluded_full_closure_rows"):
        excluded[name] = {
            asset: sum(int(part.receipt["denominator_calendar"][name][asset])
                       for part in parts)
            for asset in C.ASSETS
        }
    first_window = parts[0].receipt["corpus_window"]
    maximum = int(parts[-1].receipt["corpus_window"]["maximum_d8"])
    minimum = first_window["minimum_d8_exclusive"]
    chain = {
        "schema": "entry-v2-corpus-window-chain-v1",
        "parts": chain_parts,
    }
    chain["chain_sha256"] = C.object_sha256(chain)
    source_lineage = C.object_sha256({
        "event_sources": [[source.asset, source.d8, source.source_sha256,
                           source.sidecar_sha256] for source in ordered_sources],
        "candidate_receipts": sorted(candidate_receipts),
        "teacher_receipts": sorted(teacher_receipts),
        "forecast_receipt": reference["forecast_receipt_sha256"],
        "context_receipts": dict(sorted(context_receipts.items())),
        "qre2_calendar_authority": C.QRE2_CALENDAR_SHA256,
        "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
        "maximum_d8": maximum,
        "minimum_d8_exclusive": minimum,
        "full_manifest_authorities": reference_authorities,
    })
    receipt = dict(reference)
    receipt.pop("receipt_sha256", None)
    receipt.update({
        "artifacts": sorted(artifacts_by_asset.values(), key=lambda row: row["asset"]),
        "sessions": len(expected_sessions),
        "verified_session_warm_hits": sum(int(
            part.receipt["verified_session_warm_hits"]) for part in parts),
        "verified_session_cold_publishes": sum(int(
            part.receipt["verified_session_cold_publishes"]) for part in parts),
        "model_array_bytes_materialized": sum(int(
            part.receipt["model_array_bytes_materialized"]) for part in parts),
        "model_array_bytes_reused": sum(int(
            part.receipt["model_array_bytes_reused"]) for part in parts),
        "physical_full_pack_opens": sum(int(
            part.receipt["physical_full_pack_opens"]) for part in parts),
        "model_array_physical_fills": sum(int(
            part.receipt["model_array_physical_fills"]) for part in parts),
        "warm_corpus_ready": all(
            part.receipt["warm_corpus_ready"] is True for part in parts),
        "corpus_window": {
            **dict(first_window),
            "maximum_d8": maximum,
            "observed_end_d8": max(int(
                part.receipt["corpus_window"]["observed_end_d8"]
            ) for part in parts),
            "window_chain": chain,
        },
        "denominator_calendar": {
            **dict(reference["denominator_calendar"]), **excluded,
        },
        "asset_day_regimes": {
            "law": reference["asset_day_regimes"]["law"],
            "resolved": len(regimes),
            "expected": len({(row.asset, row.trading_day)
                             for row in expected_sessions}),
            "declarations": [{
                "asset": row.asset, "trading_day": row.trading_day,
                "regime": row.regime,
                "availability_ts_ns": row.availability_ts_ns,
            } for row in regimes],
        },
        "candidate_batches": len(sessions),
        "clear_ready_candidates": len(teacher_paths),
        "clear_typed_no_sane_suffix": typed_no_suffix,
        "compliance_counts": compliance,
        "used_forecast_lineage_sha256": C.object_sha256(sorted(forecast_lineage)),
        "prefix_verification": {
            "law": reference["prefix_verification"]["law"],
            "unique_cutoffs": sum(int(part.receipt["prefix_verification"][
                "unique_cutoffs"]) for part in parts),
            "bytes_hashed": sum(int(part.receipt["prefix_verification"][
                "bytes_hashed"]) for part in parts),
        },
        "session_stream_receipt_aggregate_sha256": stream_hash,
        "corpus_source_lineage_sha256": source_lineage,
        "raw_prefix_fidelity": {
            "expected_events": raw_evidence.expected_events,
            "observed_events": raw_evidence.observed_events,
            "mismatched_events": raw_evidence.mismatched_events,
            "source_receipt_sha256": raw_evidence.source_receipt_sha256,
            "pack_receipt_sha256": raw_evidence.pack_receipt_sha256,
        },
        "teacher_alignment": {
            "expected_candidates": teacher_evidence.expected_candidates,
            "matched_candidates": teacher_evidence.matched_candidates,
            "mismatched_candidates": teacher_evidence.mismatched_candidates,
            "teacher_receipt_sha256": teacher_evidence.teacher_receipt_sha256,
            "join_receipt_sha256": teacher_evidence.join_receipt_sha256,
        },
        "teacher_store_sha256": teacher_store.store_hash,
        "teacher_action_contract": {
            **dict(reference["teacher_action_contract"]),
            "expected_asset_days": len({(row.asset, row.trading_day)
                                        for row in expected_sessions}),
        },
        "session_specs": session_receipts,
    })
    if merged_coverage is not None:
        attached_hashes = sorted(
            str(value) for value in selected_horizon_hashes
            if isinstance(value, str)
        )
        if len(attached_hashes) != int(
                merged_coverage["suffix_attached_session_count"]):
            raise C.EntryV2Refusal(
                "chronological selected-horizon tensor count differs from coverage"
            )
        receipt.update({
            "selected_horizon_coverage_schema":
                SELECTED_HORIZON_COVERAGE_SCHEMA,
            "selected_horizon_coverage_law": SELECTED_HORIZON_COVERAGE_LAW,
            "selected_horizon_coverage_law_sha256":
                SELECTED_HORIZON_COVERAGE_LAW_SHA256,
            "selected_horizon_start_d8": int(merged_coverage["start_d8"]),
            "selected_horizon_coverage": dict(merged_coverage),
            "selected_horizon_coverage_sha256":
                merged_coverage["receipt_sha256"],
        })
        receipt["selected_horizon_tensors_aggregate_sha256"] = C.object_sha256(
            attached_hashes
        )
    else:
        receipt.pop("selected_horizon_tensors_aggregate_sha256", None)
    receipt["receipt_sha256"] = C.object_sha256(receipt)
    binding = ModelInputBinding(
        tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS), tuple(CATEGORY_SIZES),
        MODEL_ARRAYS_CONVERSION_LAW_SHA256, stream_hash,
        receipt["receipt_sha256"], source_lineage,
        str(reference["clock_law_receipt_sha256"]),
    )
    binding.validate()
    return EntryCorpus(
        tuple(sessions), teacher_store, replay, raw_evidence, teacher_evidence,
        CANDIDATE_FEATURE_SCHEMA, MappingProxyType(receipt), binding,
        _CorpusMergeProvenance(
            tuple(sorted(candidate_ids)), tuple(candidate_receipts),
            tuple(teacher_receipts), tuple(sidecar_hashes), tuple(forecast_lineage),
        ),
    )


def write_corpus_receipt(corpus: EntryCorpus, path: str | Path) -> str:
    """Publish the already-canonical corpus receipt under an allowed root."""
    return C.atomic_json(path, dict(corpus.receipt))


__all__ = [
    "AssetArtifactSet",
    "AssetScopedForecastProvider",
    "CANDIDATE_FEATURE_SCHEMA",
    "CORPUS_SCHEMA",
    "CORPUS_WINDOW_LAW_SHA256",
    "CORPUS_WINDOW_SCHEMA",
    "VERIFIED_SESSION_LAW_SHA256",
    "EntryCorpus",
    "ExplicitForecastRows",
    "FORECAST_FEATURE_FIELDS",
    "FORECAST_SCHEMA",
    "ForecastProvider",
    "ForecastQuery",
    "ForecastRow",
    "ForecastSegmentSnapshot",
    "QRE2ForecastArtifactInput",
    "QRE2ForecastProvider",
    "TeacherAlignmentRefusal",
    "build_corpus",
    "merge_asset_corpora",
    "merge_chronological_corpora",
    "write_corpus_receipt",
]
