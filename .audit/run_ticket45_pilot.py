#!/usr/bin/env python3
"""Run the bounded ticket 45 corpus pilot and publish its evidence."""

from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "16"

import numpy as np

from engine.entry_v2 import common as C
from engine.entry_v2.confirmation_plane import _SessionPlane
from engine.entry_v2.confirmation_types import ConfirmationAnchor
from engine.entry_v2.context_sources import (
    CausalContextRepository,
    TABULAR_CONTEXT_FEATURE_NAMES,
    load_context_repository,
    tabular_context_summary,
)
from engine.entry_v2.corpus import (
    VERIFIED_SESSION_LAW_SHA256,
    _verified_session_identity,
    build_corpus,
)
from engine.entry_v2.corpus_artifacts import AssetArtifactSet
from engine.entry_v2.corpus_forecast import (
    FORECAST_FEATURE_FIELDS,
    ForecastQuery,
    QRE2ForecastArtifactInput,
    QRE2ForecastProvider,
    _forecast_features,
)
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER
from engine.entry_v2.diagnostic_inputs import (
    ActionMaskReason,
    CandidateTruthBinding,
    UNITS_PER_USD,
    build_event_truth_columns,
)
from engine.entry_v2.durable_store import DurableEntryV2Store
from engine.entry_v2.event_pack import UNDEF_PRICE, EventPack
from engine.entry_v2.session_stream import SessionArrayCache
from engine.entry_v2.tabular_delayed_features import (
    SAMPLE_ORACLE,
    CausalFeatureShard,
)


DAY = 20220102
ASSET = "SI"
WORKERS = 16
if C.REPO_ROOT.resolve() != ROOT:
    raise RuntimeError(f"repository root differs: expected={ROOT} actual={C.REPO_ROOT}")
SOURCE_ROOT = ROOT / "artifacts/cache/port/entry_v2"
SESSION_ROOT = ROOT / "artifacts/cache/corpus_2022_2024/sessions"
DENSE_ROOT = ROOT / "artifacts/entry_v2/tabular_recovery/dense_store"
AUDIT_ROOT = ROOT / ".audit"
RECEIPT_PATH = AUDIT_ROOT / "ticket45-one-session-pilot.json"
FEATURE_SHARD_PATH = (
    ROOT / "artifacts/entry_v2/ticket45/schema-probe-SI-20220102.npz"
)
DURABLE_ROOT = AUDIT_ROOT / "ticket45-durable-SI-20220102"
LOCKED_WEEKEND_RECEIPT = AUDIT_ROOT / "ticket45-one-session-pilot.json"


def _previous_d8(day: int) -> int:
    parsed = datetime.strptime(f"{int(day):08d}", "%Y%m%d")
    return int((parsed - timedelta(days=1)).strftime("%Y%m%d"))


_CACHE_FLOOR_BYTES = 16 * 1024 * 1024
_CACHE_CAP_BYTES = 256 * 1024 * 1024
_CACHE_BYTES_PER_EVENT = 133


def _session_array_cache_bytes(event_count: int) -> int:
    if event_count < 0:
        raise C.EntryV2Refusal(
            "session array cache needs a nonnegative event count, "
            f"got {event_count}"
        )
    planned = int(event_count) * _CACHE_BYTES_PER_EVENT + 1
    if planned < _CACHE_FLOOR_BYTES:
        return _CACHE_FLOOR_BYTES
    if planned > _CACHE_CAP_BYTES:
        return _CACHE_CAP_BYTES
    return planned


def _selected_event_count(source_audit: SourceAudit) -> int:
    assets = source_audit.facts.get("assets")
    if not isinstance(assets, Mapping):
        raise C.EntryV2Refusal(
            "source audit assets must be a mapping, "
            f"got {type(assets).__name__}"
        )
    selected = assets.get(ASSET)
    if not isinstance(selected, Mapping):
        raise C.EntryV2Refusal(f"source audit is missing selected asset {ASSET}")
    raw = selected.get("event_count")
    if type(raw) is not int:
        raise C.EntryV2Refusal(
            "selected day event_count must be int, "
            f"got {type(raw).__name__}={raw!r}"
        )
    return raw


def _assert_one_day_window(minimum_d8_exclusive: int, maximum_d8: int) -> None:
    if _previous_d8(maximum_d8) != int(minimum_d8_exclusive):
        raise C.EntryV2Refusal(
            "ticket 45 pilot window must be exactly one day, "
            f"got minimum_d8_exclusive={minimum_d8_exclusive} "
            f"maximum_d8={maximum_d8}"
        )


def _configure_pilot(asset: str, day: int) -> None:
    global DAY, ASSET, RECEIPT_PATH, FEATURE_SHARD_PATH, DURABLE_ROOT
    name = str(asset).upper()
    if name not in C.ASSETS:
        raise C.EntryV2Refusal(
            f"asset must be one of {C.ASSETS}, got {asset!r}"
        )
    chosen_day = int(day)
    C.guard_date(chosen_day)
    C.guard_date(_previous_d8(chosen_day))
    DAY = chosen_day
    ASSET = name
    RECEIPT_PATH = AUDIT_ROOT / f"ticket45-{ASSET}-{DAY}-cache.json"
    FEATURE_SHARD_PATH = (
        ROOT / f"artifacts/entry_v2/ticket45/schema-probe-{ASSET}-{DAY}.npz"
    )
    DURABLE_ROOT = AUDIT_ROOT / f"ticket45-durable-{ASSET}-{DAY}"
    locked = {
        LOCKED_WEEKEND_RECEIPT.resolve(),
        (AUDIT_ROOT / "ticket45-HG-20221003.json").resolve(),
    }
    if RECEIPT_PATH.resolve() in locked:
        raise C.EntryV2Refusal(
            f"refusing to overwrite locked receipt: {RECEIPT_PATH}"
        )


@dataclass(frozen=True, slots=True)
class SourceAudit:
    facts: Mapping[str, object]
    candidate_row: Mapping[str, str]
    teacher_row: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class OracleProbe:
    feature_names: tuple[str, ...]
    feature_values: np.ndarray
    opportunity_id: str
    series_id: str
    candidate_id: str
    snapshot_ts_ns: int
    event_cutoff: int
    entry_event_ordinal: int
    entry_availability_ts_ns: int
    watch_age_sec: float
    feature_receipt_sha256: str
    source_receipts: tuple[str, ...]
    prior_receipt_sha256: str
    prior_present: float
    event_pack_sha256: str


@contextmanager
def _stage(
    stages: dict[str, object], name: str,
) -> Iterator[dict[str, object]]:
    record: dict[str, object] = {"status": "PASS"}
    started = time.perf_counter()
    stages[name] = record
    try:
        yield record
    except BaseException:
        record["status"] = "ERROR"
        raise
    finally:
        record["wall_seconds"] = round(time.perf_counter() - started, 6)


def _read_json_object(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal(f"JSON payload is not an object: {path}")
    return value


def _versioned_tsv_rows(path: Path) -> tuple[dict[str, str], ...]:
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeError) as exc:
        raise C.EntryV2Refusal(f"cannot read TSV: {path}") from exc
    if len(lines) < 2 or not lines[0].startswith("# QRE2"):
        raise C.EntryV2Refusal(f"versioned TSV header differs: {path}")
    rows = tuple(csv.DictReader(lines[1:], delimiter="\t"))
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise C.EntryV2Refusal(f"TSV row width differs: {path}")
    return tuple({str(key): str(value) for key, value in row.items()} for row in rows)


def _manifest_row(path: Path, day: int) -> dict[str, str]:
    matches = tuple(row for row in _versioned_tsv_rows(path) if int(row["d8"]) == day)
    if len(matches) != 1:
        raise C.EntryV2Refusal(
            f"manifest needs one row for day {day}, got {len(matches)}: {path}"
        )
    return matches[0]


def _first_ready_forecast_day(path: Path) -> int | None:
    ready = [
        int(row["d8"])
        for row in _versioned_tsv_rows(path)
        if row.get("status") == "READY"
    ]
    return min(ready) if ready else None


def _forecast_service_start_day() -> int:
    path = ROOT / "artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv"
    try:
        with path.open(newline="") as handle:
            rows = csv.DictReader(handle, delimiter="\t")
            days = [int(str(row["day"]).replace("-", "")) for row in rows]
    except (OSError, UnicodeError, KeyError, ValueError) as exc:
        raise C.EntryV2Refusal(
            f"cannot resolve forecast service start: {path}"
        ) from exc
    if not days:
        raise C.EntryV2Refusal(f"forecast service is empty: {path}")
    return min(days)


def _stored_array_bytes(metadata: Mapping[str, object]) -> int:
    arrays = metadata.get("arrays")
    if not isinstance(arrays, list):
        raise C.EntryV2Refusal(
            f"QRSESS1 arrays must be a list, got {type(arrays).__name__}"
        )
    end = 0
    for descriptor_index, raw in enumerate(arrays):
        if not isinstance(raw, dict):
            raise C.EntryV2Refusal(
                "QRSESS1 array descriptor must be an object, "
                f"got index={descriptor_index} type={type(raw).__name__}"
            )
        dtype = np.dtype(str(raw["dtype"]))
        end = max(end, int(raw["offset"]) + int(raw["count"]) * dtype.itemsize)
    return end


def _audit_sources() -> SourceAudit:
    assets: dict[str, object] = {}
    selected_candidate: Mapping[str, str] | None = None
    selected_teacher: Mapping[str, str] | None = None
    for asset in C.ASSETS:
        session_json = SESSION_ROOT / asset / f"{DAY}.json"
        session_bin = SESSION_ROOT / asset / f"{DAY}.bin"
        session = _read_json_object(session_json)
        if session.get("format") != "QRSESS1":
            raise C.EntryV2Refusal(f"QRSESS1 format differs: {session_json}")
        expected_bytes = _stored_array_bytes(session)
        if not session_bin.is_file() or session_bin.stat().st_size != expected_bytes:
            raise C.EntryV2Refusal(f"QRSESS1 binary size differs: {session_bin}")
        candidate_manifest = SOURCE_ROOT / f"g1/candidates/{asset}/manifest.tsv"
        teacher_manifest = SOURCE_ROOT / f"g1/teacher/{asset}/manifest.tsv"
        candidate = _manifest_row(candidate_manifest, DAY)
        teacher = _manifest_row(teacher_manifest, DAY)
        candidate_path = SOURCE_ROOT / candidate["candidate_file"]
        teacher_path = SOURCE_ROOT / teacher["teacher_file"]
        candidate_rows = _versioned_tsv_rows(candidate_path)
        teacher_rows = _versioned_tsv_rows(teacher_path)
        if (
            len(candidate_rows) != int(candidate["rows"])
            or len(teacher_rows) != int(teacher["rows"])
        ):
            raise C.EntryV2Refusal(f"G1 row count differs for {asset}/{DAY}")
        candidate_receipt_path = SOURCE_ROOT / candidate["receipt_file"]
        teacher_receipt_path = SOURCE_ROOT / teacher["receipt_file"]
        if (
            C.file_sha256(candidate_receipt_path) != candidate["receipt_sha256"]
            or C.file_sha256(teacher_receipt_path) != teacher["receipt_sha256"]
        ):
            raise C.EntryV2Refusal(f"G1 receipt hash differs for {asset}/{DAY}")
        candidate_receipt = _read_json_object(candidate_receipt_path)
        teacher_receipt = _read_json_object(teacher_receipt_path)
        event_sidecar = _read_json_object(
            SOURCE_ROOT / f"events/{asset}/{DAY}.qre2.json"
        )
        assets[asset] = {
            "calendar_disposition": C.denominator_disposition(asset, DAY),
            "substrate_json": str(session_json),
            "substrate_bin": str(session_bin),
            "substrate_bytes": session_bin.stat().st_size,
            "valid_seconds": int(
                dict(session.get("meta", {})).get("n_valid_seconds", -1)
            ),
            "event_pack": str(SOURCE_ROOT / f"events/{asset}/{DAY}.qre2"),
            "event_count": int(event_sidecar.get("event_count", -1)),
            "candidate_status": candidate["status"],
            "candidate_rows": len(candidate_rows),
            "teacher_rows": len(teacher_rows),
            "g1_confirmations": int(candidate_receipt.get("confirmations", -1)),
            "generation_action": "SKIPPED_ALREADY_GENERATED",
            "candidate_receipt_path": str(candidate_receipt_path),
            "candidate_receipt_sha256": candidate["receipt_sha256"],
            "teacher_receipt_path": str(teacher_receipt_path),
            "teacher_receipt_sha256": teacher["receipt_sha256"],
            "teacher_ready": int(teacher_receipt.get("ready", -1)),
            "teacher_typed_no_sane_suffix": int(
                teacher_receipt.get("typed_no_sane_suffix", -1)
            ),
        }
        if asset == ASSET:
            selected_candidate = candidate
            selected_teacher = teacher
    if selected_candidate is None or selected_teacher is None:
        raise C.EntryV2Refusal(f"selected asset is absent: {ASSET}")
    return SourceAudit(
        facts={
            "day": DAY,
            "selected_asset": ASSET,
            "workers": WORKERS,
            "assets": assets,
        },
        candidate_row=selected_candidate,
        teacher_row=selected_teacher,
    )


def _forecast_provider() -> QRE2ForecastProvider:
    artifact = SOURCE_ROOT / f"forecast/{ASSET}.qrf4.tsv"
    receipt = SOURCE_ROOT / f"forecast/{ASSET}.qrf4.json"
    return QRE2ForecastProvider(
        (
            QRE2ForecastArtifactInput(
                SOURCE_ROOT,
                ASSET,
                C.file_sha256(artifact),
                C.file_sha256(receipt),
            ),
        )
    )


def _forecast_audit(provider: QRE2ForecastProvider) -> Mapping[str, object]:
    with EventPack(
        SOURCE_ROOT / f"events/{ASSET}/{DAY}.qre2", verify_hash=True
    ) as pack:
        event_ts_ns = int(pack.rows[0]["ts_recv_ns"])
    query = ForecastQuery(
        "ticket45-forecast-probe", ASSET, DAY, event_ts_ns + 1, 1
    )
    row = provider.forecast(query)
    if row is None:
        return {
            "gate": "REFUSED",
            "message": f"forecast row is absent for {ASSET}/{DAY}",
            "native_consumer_behavior": "REFUSED",
            "forecast_service_start_day": _forecast_service_start_day(),
            "qre2_first_ready_day": _first_ready_forecast_day(
                SOURCE_ROOT / f"forecast/{ASSET}.qrf4.tsv"
            ),
        }
    native_behavior = "REFUSED"
    native_feature_count = 0
    try:
        features, _lineage = _forecast_features(provider, query)
        native_behavior = "BOUND" if (
            row.session.status == "READY" and row.phase_segment.status == "READY"
        ) else "MASKED_MISSING"
        native_feature_count = len(features)
    except C.EntryV2Refusal:
        pass
    unavailable = (
        row.session.status != "READY" or row.phase_segment.status != "READY"
    )
    return {
        "gate": "REFUSED" if unavailable else "BOUND",
        "message": (
            f"forecast context unavailable for {ASSET}/{DAY}; "
            f"session={row.session.status} phase={row.phase_segment.status}"
            if unavailable
            else f"forecast context bound for {ASSET}/{DAY}"
        ),
        "session_status": row.session.status,
        "phase_status": row.phase_segment.status,
        "native_consumer_behavior": native_behavior,
        "native_feature_count": native_feature_count,
        "silent_skip_defect": unavailable and native_behavior == "MASKED_MISSING",
        "forecast_service_start_day": _forecast_service_start_day(),
        "qre2_first_ready_day": _first_ready_forecast_day(
            SOURCE_ROOT / f"forecast/{ASSET}.qrf4.tsv"
        ),
    }


def _first_sane_oracle_row(pack: EventPack) -> tuple[int, np.void]:
    close_ns = int(pack.header.close_utc) * 1_000_000_000
    undefined = int(UNDEF_PRICE)
    for index, row in enumerate(pack.rows):
        bid = int(row["bid_px"])
        ask = int(row["ask_px"])
        snapshot = int(row["ts_recv_ns"]) + 2
        if (
            bid > 0
            and bid != undefined
            and ask != undefined
            and ask > bid
            and snapshot < close_ns
        ):
            return index, row
    raise C.EntryV2Refusal(
        f"oracle probe found no sane book on {ASSET}/{DAY}"
    )


def _oracle_probe(
    context_repository: CausalContextRepository,
    provider: QRE2ForecastProvider,
) -> OracleProbe:
    event_path = SOURCE_ROOT / f"events/{ASSET}/{DAY}.qre2"
    with EventPack(event_path, verify_hash=True) as pack:
        entry_event_ordinal, row = _first_sane_oracle_row(pack)
        event_cutoff = entry_event_ordinal + 1
        availability = int(row["ts_recv_ns"])
        decision = availability + 1
        snapshot = availability + 2
        bid = int(row["bid_px"])
        ask = int(row["ask_px"])
        mid2 = bid + ask
        spread = (ask - bid) * 1e-9 * ASSET_MULTIPLIER[ASSET]
        cost = spread + 5.0
        candidate_id = "ticket45-oracle-schema-probe"
        binding = CandidateTruthBinding(
            candidate_id=candidate_id,
            asset=ASSET,
            trading_day=DAY,
            decision_ts_ns=decision,
            event_cutoff=event_cutoff,
            prefix_last_event_ordinal=entry_event_ordinal,
            phase="0",
            phase_open_ts_ns=pack.header.open_ns,
            phase_close_ts_ns=pack.header.close_utc * 1_000_000_000,
            side=1,
            entry_bid_px=bid,
            entry_ask_px=ask,
            entry_mid2=mid2,
            multiplier=ASSET_MULTIPLIER[ASSET],
            frozen_cost_units=int(round(cost * UNITS_PER_USD)),
            sane_ceiling=Decimal("250"),
            sane_ceiling_units=250 * UNITS_PER_USD,
            compliance_status="CLEAR",
            teacher_status="NO_SANE_SUFFIX",
            cert_close_units=0,
            mfe_units=0,
            mae_units=0,
            exit_ts_ns=0,
            wall_hit=False,
            payer=False,
            native_candidate_local=False,
            action_target=False,
            action_loss_mask=False,
            action_mask_reason=ActionMaskReason.NO_SANE_SUFFIX,
        )
        truth = build_event_truth_columns(pack.rows, ASSET, (binding,))
        plane = _SessionPlane(
            pack,
            truth.candidate_columns(binding),
            prior_session_context=None,
        )
        candidate: dict[str, str | float] = {
            "candidate_id": candidate_id,
            "decision_sec": str(
                (decision - pack.header.open_ns) // 1_000_000_000
            ),
            "entry_mid2": str(mid2),
            "entry_bid_px": str(bid),
            "entry_ask_px": str(ask),
            "phase_open_utc": str(pack.header.open_utc),
            "phase_close_utc": str(pack.header.close_utc),
            "decision_ts_ns": str(decision),
            "atr14_prev_usd": "0",
            "entry_spread_usd": str(spread),
            "frozen_cost_usd": str(cost),
            "spread_prior_usd": "0",
            "spread_prior_present": "0",
            "rung_mask": "1",
            "delay": "STANDARD_120",
        }
        candidate.update({name: 0.0 for name in FORECAST_FEATURE_FIELDS})
        opportunity_id = C.object_sha256(
            {
                "schema": "QRE2TICKET45ORACLE1",
                "asset": ASSET,
                "d8": DAY,
                "snapshot_ts_ns": snapshot,
            }
        )
        series_id = C.object_sha256(
            {
                "schema": "QRE2TICKET45SERIES1",
                "asset": ASSET,
                "d8": DAY,
            }
        )
        prior_receipt = C.object_sha256(
            {
                "schema": "QRE2CONFPRIORABSENT1",
                "asset": ASSET,
                "trading_day": DAY,
            }
        )
        context_receipt = str(
            context_repository.receipt.get("receipt_sha256", "")
        )
        source_receipts = (
            str(pack.sidecar["event_pack_sha256"]),
            provider.receipt_sha256,
            prior_receipt,
            context_receipt,
        )
        feature_receipt = C.object_sha256(
            {
                "schema": "QRE2TICKET45FEATURE1",
                "opportunity_id": opportunity_id,
                "source_receipts": source_receipts,
            }
        )
        anchor = ConfirmationAnchor(
            opportunity_id=opportunity_id,
            series_id=series_id,
            candidate_ids=(candidate_id,),
            asset=ASSET,
            trading_day=DAY,
            side=1,
            phase="0",
            phase_close_ts_ns=pack.header.close_utc * 1_000_000_000,
            snapshot_ts_ns=snapshot,
            event_cutoff=event_cutoff,
            entry_event_ordinal=entry_event_ordinal,
            entry_availability_ts_ns=availability,
            entry_bid_px=bid,
            entry_ask_px=ask,
            entry_mid2=mid2,
            entry_spread_usd=spread,
            frozen_cost_usd=cost,
            min_alert_age_sec=(snapshot - decision) / 1_000_000_000,
            max_alert_age_sec=(snapshot - decision) / 1_000_000_000,
            feature_receipt_sha256=feature_receipt,
        )
        base = plane.feature_map(anchor, (binding,), (candidate,))
        context = tabular_context_summary(
            context_repository, DAY, (snapshot,)
        )[0]
        names = tuple(base) + TABULAR_CONTEXT_FEATURE_NAMES
        values = np.concatenate(
            (
                np.asarray(tuple(base.values()), np.float32),
                np.asarray(context, np.float32),
            )
        )
    if values.shape != (len(names),) or not np.all(np.isfinite(values)):
        raise C.EntryV2Refusal(
            "Oracle schema probe must be finite and match its names, "
            f"got shape={values.shape} expected={(len(names),)} "
            f"finite={bool(np.all(np.isfinite(values)))}"
        )
    return OracleProbe(
        feature_names=names,
        feature_values=values,
        opportunity_id=opportunity_id,
        series_id=series_id,
        candidate_id=candidate_id,
        snapshot_ts_ns=snapshot,
        event_cutoff=1,
        entry_event_ordinal=0,
        entry_availability_ts_ns=availability,
        watch_age_sec=(snapshot - decision) / 1_000_000_000,
        feature_receipt_sha256=feature_receipt,
        source_receipts=source_receipts,
        prior_receipt_sha256=prior_receipt,
        prior_present=float(base["disc_prior_present"]),
        event_pack_sha256=str(source_receipts[0]),
    )


def _reference_feature_names() -> tuple[tuple[str, ...], Mapping[str, object]]:
    metadata_paths = sorted(DENSE_ROOT.glob(f"*/{ASSET}/20210721.json"))
    for metadata_path in metadata_paths:
        metadata = _read_json_object(metadata_path)
        raw_artifact = metadata.get("artifact_path")
        if not isinstance(raw_artifact, str):
            continue
        artifact = Path(raw_artifact).resolve()
        try:
            artifact.relative_to(DENSE_ROOT.resolve())
        except ValueError:
            continue
        if not artifact.is_file():
            continue
        with np.load(artifact, allow_pickle=False) as stored:
            if str(stored["schema"][0]) != "QRE2TABFEATURESHARD2":
                continue
            names = tuple(stored["feature_names"].astype(str).tolist())
            representation = str(stored["representation_sha256"][0])
        artifact_sha = C.file_sha256(artifact)
        expected_sha = str(metadata.get("artifact_sha256", ""))
        if artifact_sha != expected_sha:
            raise C.EntryV2Refusal(
                f"2021 reference shard hash differs for {artifact}: "
                f"expected={expected_sha} actual={artifact_sha}"
            )
        return names, {
            "metadata_path": str(metadata_path),
            "artifact_path": str(artifact),
            "artifact_sha256": artifact_sha,
            "representation_sha256": representation,
            "day": 20210721,
        }
    raise C.EntryV2Refusal(
        "strict 2021 feature shard reference is absent, "
        f"expected pattern=*/{ASSET}/20210721.json under {DENSE_ROOT} "
        f"and inspected={len(metadata_paths)}"
    )


def _compare_feature_names(
    reference: Sequence[str], current: Sequence[str],
) -> Mapping[str, object]:
    reference_tuple = tuple(reference)
    current_tuple = tuple(current)
    mismatch = next(
        (
            index
            for index, values in enumerate(zip(reference_tuple, current_tuple))
            if values[0] != values[1]
        ),
        None,
    )
    if mismatch is None and len(reference_tuple) != len(current_tuple):
        mismatch = min(len(reference_tuple), len(current_tuple))
    reference_set = set(reference_tuple)
    current_set = set(current_tuple)
    return {
        "exact_order_match": reference_tuple == current_tuple,
        "reference_count": len(reference_tuple),
        "current_count": len(current_tuple),
        "reference_sha256": C.object_sha256(list(reference_tuple)),
        "current_sha256": C.object_sha256(list(current_tuple)),
        "first_mismatch_index": mismatch,
        "removed": [name for name in reference_tuple if name not in current_set],
        "added": [name for name in current_tuple if name not in reference_set],
    }


def _publish_probe_shard(probe: OracleProbe) -> Mapping[str, object]:
    shard = CausalFeatureShard(
        feature_names=probe.feature_names,
        features=probe.feature_values.reshape(1, -1),
        opportunity_id=np.asarray([probe.opportunity_id], str),
        series_id=np.asarray([probe.series_id], str),
        candidate_id=np.asarray([probe.candidate_id], str),
        asset=np.asarray([ASSET], str),
        day=np.asarray([DAY], np.int64),
        side=np.asarray([1], np.int8),
        phase=np.asarray(["0"], str),
        snapshot_ts_ns=np.asarray([probe.snapshot_ts_ns], np.int64),
        event_cutoff=np.asarray([probe.event_cutoff], np.int64),
        entry_event_ordinal=np.asarray(
            [probe.entry_event_ordinal], np.int64
        ),
        entry_availability_ts_ns=np.asarray(
            [probe.entry_availability_ts_ns], np.int64
        ),
        watch_age_sec=np.asarray([probe.watch_age_sec], np.float32),
        sampling_reason=np.asarray([SAMPLE_ORACLE], np.int16),
        feature_receipt_sha256=np.asarray(
            [probe.feature_receipt_sha256], str
        ),
        base_config_sha256=C.object_sha256(
            {
                "schema": "QRE2TICKET45PROBECONFIG1",
                "asset": ASSET,
                "d8": DAY,
                "prior_session_context": None,
            }
        ),
        sampling_receipt_sha256=C.object_sha256(
            {
                "schema": "QRE2TICKET45SAMPLING1",
                "reason": "ORACLE_SCHEMA_PROBE",
                "opportunity_id": probe.opportunity_id,
            }
        ),
        source_receipts=probe.source_receipts,
    )
    shard.validate()
    reused = False
    if FEATURE_SHARD_PATH.exists():
        stored = CausalFeatureShard.load(FEATURE_SHARD_PATH)
        if stored.representation_sha256 != shard.representation_sha256:
            raise C.EntryV2Refusal(
                f"existing probe shard differs: {FEATURE_SHARD_PATH}"
            )
        reused = True
    else:
        shard.save(FEATURE_SHARD_PATH)
    reloaded = CausalFeatureShard.load(FEATURE_SHARD_PATH)
    if reloaded.representation_sha256 != shard.representation_sha256:
        raise C.EntryV2Refusal(
            f"probe shard strict reload differs for {FEATURE_SHARD_PATH}: "
            f"expected={shard.representation_sha256} "
            f"actual={reloaded.representation_sha256}"
        )
    return {
        "path": str(FEATURE_SHARD_PATH),
        "artifact_sha256": C.file_sha256(FEATURE_SHARD_PATH),
        "representation_sha256": reloaded.representation_sha256,
        "strict_reloaded": True,
        "reused": reused,
        "rows": len(reloaded.features),
        "feature_count": len(reloaded.feature_names),
        "classification": "DIAGNOSTIC_SCHEMA_PROBE_NOT_AUTHORITATIVE_G1",
    }


def _asset_artifact_set() -> AssetArtifactSet:
    return AssetArtifactSet(
        SOURCE_ROOT,
        ASSET,
        C.file_sha256(SOURCE_ROOT / f"g1/candidates/{ASSET}/manifest.tsv"),
        C.file_sha256(SOURCE_ROOT / f"g1/teacher/{ASSET}/manifest.tsv"),
        C.file_sha256(SOURCE_ROOT / f"g1/receipts/{ASSET}.candidates.json"),
        C.file_sha256(SOURCE_ROOT / f"g1/receipts/{ASSET}.teacher.json"),
    )


def _run_build_corpus(
    context_repository: CausalContextRepository,
    provider: QRE2ForecastProvider,
    source_audit: SourceAudit,
) -> tuple[Mapping[str, object], Mapping[str, object], bool]:
    identity = _verified_session_identity(
        ASSET,
        DAY,
        source_audit.candidate_row,
        source_audit.teacher_row,
    )
    store = DurableEntryV2Store(DURABLE_ROOT)
    preexisting = store.has_product(
        "verified-sessions", identity, VERIFIED_SESSION_LAW_SHA256
    )
    exclusive_minimum = _previous_d8(DAY)
    _assert_one_day_window(exclusive_minimum, DAY)
    window = {
        "maximum_d8": DAY,
        "minimum_d8_exclusive": exclusive_minimum,
    }
    event_count = _selected_event_count(source_audit)
    cache_bytes = _session_array_cache_bytes(event_count)
    cache = SessionArrayCache(cache_bytes, durable_store=store)
    build_result: dict[str, object]
    try:
        try:
            corpus = build_corpus(
                (_asset_artifact_set(),),
                {ASSET: context_repository},
                provider,
                require_assets=(ASSET,),
                array_cache=cache,
                maximum_d8=DAY,
                minimum_d8_exclusive=exclusive_minimum,
            )
        except C.EntryV2Refusal as exc:
            build_result = {
                "status": "REFUSED",
                "message": str(exc),
                "called": True,
                "corpus_window": window,
                "session_array_cache_bytes": cache_bytes,
                "session_array_cache_event_count": event_count,
            }
        else:
            build_result = {
                "status": "PASS",
                "called": True,
                "sessions": len(corpus.sessions),
                "receipt_sha256": corpus.receipt["receipt_sha256"],
                "corpus_window": window,
                "session_array_cache_bytes": cache_bytes,
                "session_array_cache_event_count": event_count,
            }
    finally:
        cache.close()
    return build_result, identity, preexisting


def _strict_reload_verified_product(
    identity: Mapping[str, object], preexisting: bool,
) -> Mapping[str, object]:
    reopened = DurableEntryV2Store(DURABLE_ROOT)
    product = reopened.load(
        "verified-sessions", identity, VERIFIED_SESSION_LAW_SHA256
    )
    if product is None:
        product_result: Mapping[str, object] = {
            "strict_reloaded": False,
            "published": False,
            "published_this_run": False,
            "preexisting": preexisting,
        }
    else:
        try:
            semantic = product.receipt.get("semantic")
            target_ids = (
                list(semantic.get("target_candidate_ids", ()))
                if isinstance(semantic, Mapping)
                else []
            )
            product_result = {
                "strict_reloaded": True,
                "published": True,
                "published_this_run": not preexisting,
                "preexisting": preexisting,
                "key": product.key,
                "data_path": str(product.data_path),
                "sidecar_path": str(product.sidecar_path),
                "receipt_sha256": product.receipt["receipt_sha256"],
                "data_size_bytes": int(product.receipt["data_size_bytes"]),
                "array_count": len(product.arrays),
                "target_candidate_ids": target_ids,
                "authoritative_feature_rows": len(target_ids),
            }
        finally:
            product.close()
    return product_result


def _publish_receipt(payload: dict[str, object]) -> str:
    payload["receipt_sha256"] = C.object_sha256(payload)
    raw = C.canonical_bytes(payload)
    temporary = RECEIPT_PATH.with_name(
        RECEIPT_PATH.name + f".tmp.{os.getpid()}"
    )
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, RECEIPT_PATH)
    stored = _read_json_object(RECEIPT_PATH)
    if stored != C.canonical_json_value(payload):
        raise C.EntryV2Refusal(
            f"ticket 45 receipt strict reload differs for {RECEIPT_PATH}: "
            f"expected_receipt={payload['receipt_sha256']} "
            f"actual_receipt={stored.get('receipt_sha256')}"
        )
    return str(payload["receipt_sha256"])


def _selftest() -> int:
    exact = _compare_feature_names(("a", "b"), ("a", "b"))
    drift = _compare_feature_names(("a", "b"), ("a", "c"))
    if _session_array_cache_bytes(0) != _CACHE_FLOOR_BYTES:
        raise AssertionError(
            "cache floor selftest expected "
            f"{_CACHE_FLOOR_BYTES}, got {_session_array_cache_bytes(0)}"
        )
    hg_events = 481637
    hg_bytes = hg_events * _CACHE_BYTES_PER_EVENT + 1
    if _session_array_cache_bytes(hg_events) != hg_bytes:
        raise AssertionError(
            "HG event cache selftest expected "
            f"{hg_bytes}, got {_session_array_cache_bytes(hg_events)}"
        )
    huge = (_CACHE_CAP_BYTES // _CACHE_BYTES_PER_EVENT) + 1
    if _session_array_cache_bytes(huge) != _CACHE_CAP_BYTES:
        raise AssertionError(
            "cache cap selftest expected "
            f"{_CACHE_CAP_BYTES}, got {_session_array_cache_bytes(huge)}"
        )
    if (
        exact["exact_order_match"] is not True
        or drift["exact_order_match"] is not False
        or drift["first_mismatch_index"] != 1
    ):
        raise AssertionError(
            "feature schema comparison selftest expected exact=true, "
            f"drift=false, mismatch=1; got exact={exact} drift={drift}"
        )
    with tempfile.TemporaryDirectory(
        dir=ROOT / "artifacts", prefix="ticket45-selftest-"
    ) as raw:
        path = Path(raw) / "shard.npz"
        shard = CausalFeatureShard(
            feature_names=("selftest",),
            features=np.asarray([[1.0]], np.float32),
            opportunity_id=np.asarray(["op"], str),
            series_id=np.asarray(["series"], str),
            candidate_id=np.asarray(["candidate"], str),
            asset=np.asarray([ASSET], str),
            day=np.asarray([DAY], np.int64),
            side=np.asarray([1], np.int8),
            phase=np.asarray(["0"], str),
            snapshot_ts_ns=np.asarray([2], np.int64),
            event_cutoff=np.asarray([1], np.int64),
            entry_event_ordinal=np.asarray([0], np.int64),
            entry_availability_ts_ns=np.asarray([1], np.int64),
            watch_age_sec=np.asarray([0.0], np.float32),
            sampling_reason=np.asarray([SAMPLE_ORACLE], np.int16),
            feature_receipt_sha256=np.asarray(["a" * 64], str),
            base_config_sha256="b" * 64,
            sampling_receipt_sha256="c" * 64,
            source_receipts=("d" * 64,),
        )
        shard.save(path)
        reloaded = CausalFeatureShard.load(path)
        if reloaded.representation_sha256 != shard.representation_sha256:
            raise AssertionError(
                "feature shard strict reload selftest expected "
                f"{shard.representation_sha256}, got "
                f"{reloaded.representation_sha256}"
            )
    print(
        json.dumps(
            {
                "schema": "QRE2TICKET45SELFTEST1",
                "status": "PASS",
                "tests": [
                    "feature_schema_order",
                    "causal_feature_shard_strict_reload",
                    "session_array_cache_bytes",
                ],
            },
            sort_keys=True,
        )
    )
    return 0


def _run_pilot() -> int:
    started = time.perf_counter()
    stages: dict[str, object] = {}
    with _stage(stages, "source_audit") as stage:
        source_audit = _audit_sources()
        stage["selected_candidate_rows"] = int(
            source_audit.candidate_row["rows"]
        )
        stage["selected_teacher_rows"] = int(source_audit.teacher_row["rows"])
    with _stage(stages, "forecast_provider_load") as stage:
        provider = _forecast_provider()
        stage["provider_receipt_sha256"] = provider.receipt_sha256
    with _stage(stages, "forecast_gate") as stage:
        forecast = _forecast_audit(provider)
        stage.update(forecast)
        stage["status"] = str(forecast["gate"])
    with _stage(stages, "context_repository_load") as stage:
        context_repository = load_context_repository(ASSET, DAY)
        stage["receipt_sha256"] = context_repository.receipt["receipt_sha256"]
    with _stage(stages, "prior_absent_oracle_probe") as stage:
        probe = _oracle_probe(context_repository, provider)
        stage.update(
            {
                "path": "ORACLE",
                "prior_session_context": None,
                "prior_event_path_opened": False,
                "stored_oracle_bytes": 0,
                "disc_prior_present": probe.prior_present,
                "feature_count": len(probe.feature_names),
                "prior_receipt_sha256": probe.prior_receipt_sha256,
            }
        )
    with _stage(stages, "schema_compare_before_build") as stage:
        reference_names, reference = _reference_feature_names()
        comparison = _compare_feature_names(
            reference_names, probe.feature_names
        )
        stage.update(comparison)
        stage["reference"] = reference
        stage["status"] = (
            "PASS" if comparison["exact_order_match"] else "DRIFT"
        )
    with _stage(stages, "diagnostic_feature_shard_publish") as stage:
        diagnostic_shard = _publish_probe_shard(probe)
        stage.update(diagnostic_shard)
    with _stage(stages, "build_corpus") as stage:
        build_result, verified_identity, product_preexisting = _run_build_corpus(
            context_repository, provider, source_audit
        )
        stage.update(build_result)
    with _stage(stages, "verified_session_strict_reload") as stage:
        verified_product = _strict_reload_verified_product(
            verified_identity, product_preexisting
        )
        stage.update(verified_product)
        stage["status"] = (
            "PASS" if verified_product["strict_reloaded"] else "FAIL"
        )
    forecast_ready = (
        forecast.get("gate") == "BOUND"
        and forecast.get("session_status") == "READY"
        and forecast.get("phase_status") == "READY"
    )
    silent_skip = bool(forecast.get("silent_skip_defect"))
    build_pass = build_result.get("status") == "PASS"
    authoritative_reload = bool(verified_product.get("strict_reloaded"))
    blockers = []
    if not forecast_ready:
        blockers.append(str(forecast.get("message", "forecast did not bind READY")))
    if silent_skip:
        blockers.append("silent_skip_defect")
    if not build_pass:
        blockers.append(
            f"build_corpus {str(build_result.get('status')).lower()}: "
            f"{build_result.get('message', 'no refusal message')}"
        )
    if not authoritative_reload:
        blockers.append("authoritative G1 shard did not strict-reload")
    passed = bool(
        forecast_ready and not silent_skip and build_pass and authoritative_reload
    )
    payload: dict[str, object] = {
        "schema": "QRE2TICKET45PILOT1",
        "ticket": 45,
        "day": DAY,
        "asset": ASSET,
        "workers": WORKERS,
        "source_audit": source_audit.facts,
        "forecast": forecast,
        "prior_absent": {
            "exercised": probe.prior_present == 0.0,
            "path": "ORACLE",
            "prior_session_context": None,
            "prior_event_path_opened": False,
            "stored_oracle_bytes": 0,
            "disc_prior_present": probe.prior_present,
            "receipt_sha256": probe.prior_receipt_sha256,
        },
        "schema_comparison": {
            **comparison,
            "reference": reference,
            "compared_before_build": True,
        },
        "diagnostic_feature_shard": diagnostic_shard,
        "build_corpus": build_result,
        "session_array_cache_bytes": build_result.get(
            "session_array_cache_bytes"
        ),
        "verified_session_product": verified_product,
        "stages": stages,
        "total_wall_seconds": round(time.perf_counter() - started, 6),
        "ticket_result": {
            "passed": passed,
            "authoritative_g1_feature_shard_published": authoritative_reload,
            "blockers": blockers,
        },
    }
    receipt_sha256 = _publish_receipt(payload)
    print(
        json.dumps(
            {
                "receipt": str(RECEIPT_PATH),
                "receipt_sha256": receipt_sha256,
                "ticket_passed": passed,
                "diagnostic_shard_strict_reloaded": diagnostic_shard[
                    "strict_reloaded"
                ],
                "verified_session_strict_reloaded": verified_product[
                    "strict_reloaded"
                ],
                "build_corpus": build_result["status"],
                "session_array_cache_bytes": build_result.get(
                    "session_array_cache_bytes"
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a one-day ticket 45 corpus pilot."
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run local contract checks without opening real session inputs.",
    )
    parser.add_argument(
        "--asset",
        default=ASSET,
        help="Asset for the one-day window. Default SI.",
    )
    parser.add_argument(
        "--day",
        type=int,
        default=DAY,
        help="Inclusive maximum d8. The exclusive minimum is the prior calendar day.",
    )
    args = parser.parse_args()
    if args.selftest:
        return _selftest()
    _configure_pilot(args.asset, args.day)
    return _run_pilot()


if __name__ == "__main__":
    raise SystemExit(main())
