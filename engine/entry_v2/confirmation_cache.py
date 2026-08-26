"""Persistent session caches for confirmation experiments."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation import (
    ConfirmationConfig,
    ConfirmationDataset,
    ConfirmationOpportunitySet,
    ConfirmationRefusal,
    confirmation_implementation_hashes,
    learnable_confirmation_count,
    materialize_confirmation_opportunity_session,
    materialize_confirmation_session,
    read_versioned_tsv,
    stream_conservation_receipt,
)
from .confirmation_roster import (
    AuthoritativeConfirmationSessionSpec,
    _context_repository,
    _sha,
    _source_identity,
)
from .contracts import SessionRef
from .corpus_forecast import QRE2ForecastArtifactInput, QRE2ForecastProvider
from .corpus_units import ASSET_MULTIPLIER, ASSET_RAW_TICK
from .discretionary_features import PriorSessionContext
from .event_pack import EventPack


FEATURE_CACHE_SCHEMA = "QRE2CONFFEATCACHE1"
OPPORTUNITY_CACHE_SCHEMA = "QRE2CONFOPPCACHE1"


@dataclass(frozen=True, slots=True)
class CachedConfirmationSession:
    session: SessionRef
    status: str
    manifest_path: str
    dataset_path: str | None
    dataset_representation_sha256: str | None
    receipt_sha256: str

    def __post_init__(self) -> None:
        populated = self.status == "MATERIALIZED"
        if (self.status not in {"MATERIALIZED", "NO_NATIVE_CANDIDATES",
                               "NO_LEARNABLE_CANDIDATES"}
                or populated != (self.dataset_path is not None)
                or populated
                   != (self.dataset_representation_sha256 is not None)
                or not _sha(self.receipt_sha256)):
            raise ConfirmationRefusal(
                "cached confirmation session is malformed")


_FORECAST_PROVIDER_CACHE: dict[
    tuple[str, str, str, str], QRE2ForecastProvider,
] = {}


def _forecast_provider(
    spec: AuthoritativeConfirmationSessionSpec,
) -> QRE2ForecastProvider:
    key = (
        spec.source_root,
        spec.asset,
        spec.expected_forecast_artifact_sha256,
        spec.expected_forecast_receipt_sha256,
    )
    provider = _FORECAST_PROVIDER_CACHE.get(key)
    if provider is None:
        provider = QRE2ForecastProvider((QRE2ForecastArtifactInput(
            Path(spec.source_root), spec.asset,
            spec.expected_forecast_artifact_sha256,
            spec.expected_forecast_receipt_sha256),))
        _FORECAST_PROVIDER_CACHE[key] = provider
    return provider


def _prior_session_context(
    spec: AuthoritativeConfirmationSessionSpec,
) -> PriorSessionContext | None:
    if spec.previous_event_path is None:
        return None
    with EventPack(spec.previous_event_path, verify_hash=True) as pack:
        if (pack.header.asset != spec.asset
                or pack.header.d8 != spec.previous_trading_day
                or pack.sidecar.get("event_pack_sha256")
                   != spec.expected_previous_event_sha256):
            raise ConfirmationRefusal(
                "previous event pack identity differs")
        return PriorSessionContext(
            rows=np.asarray(pack.rows),
            asset=spec.asset,
            trading_day=int(spec.previous_trading_day),
            event_pack_sha256=spec.expected_previous_event_sha256,
            raw_tick=int(ASSET_RAW_TICK[spec.asset]),
            multiplier=int(ASSET_MULTIPLIER[spec.asset]))


def _manifest(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfirmationRefusal(
            f"cannot read confirmation cache: {path}") from exc
    if not isinstance(value, dict):
        raise ConfirmationRefusal(
            "confirmation cache manifest is not an object")
    return value


def _record_from_manifest(
    path: Path,
    value: Mapping[str, object],
    *,
    schema: str,
    source: Mapping[str, object],
    config_sha256: str,
) -> CachedConfirmationSession:
    core = {
        key: item for key, item in value.items()
        if key != "receipt_sha256"
    }
    if (value.get("schema") != schema
            or value.get("source") != source
            or value.get("config_sha256") != config_sha256
            or value.get("implementation_sha256")
               != dict(confirmation_implementation_hashes())
            or value.get("receipt_sha256") != C.object_sha256(core)):
        raise ConfirmationRefusal(
            "confirmation cache identity/receipt differs")
    status = str(value.get("status"))
    session = SessionRef(
        str(source["asset"]),
        int(source["trading_day"]),
        f"{source['asset']}-{source['trading_day']}",
    )
    dataset_path = value.get("dataset_path")
    representation = value.get("dataset_representation_sha256")
    if status == "MATERIALIZED":
        if not isinstance(dataset_path, str) or not _sha(representation):
            raise ConfirmationRefusal(
                "materialized cache manifest is incomplete")
        dataset = (
            ConfirmationDataset.load(dataset_path)
            if schema == FEATURE_CACHE_SCHEMA
            else ConfirmationOpportunitySet.load(dataset_path)
        )
        if (dataset.representation_sha256 != representation
                or C.file_sha256(dataset_path) != value.get("dataset_sha256")
                or set(np.asarray(dataset.asset, str)) != {session.asset}
                or set(np.asarray(dataset.day, np.int64))
                   != {session.trading_day}):
            raise ConfirmationRefusal(
                "cached confirmation dataset differs")
    elif status in {
        "NO_NATIVE_CANDIDATES", "NO_LEARNABLE_CANDIDATES",
    }:
        if dataset_path is not None or representation is not None:
            raise ConfirmationRefusal(
                "empty cache manifest names a dataset")
    else:
        raise ConfirmationRefusal(
            "confirmation cache has an unknown status")
    return CachedConfirmationSession(
        session,
        status,
        str(path),
        dataset_path,
        representation,
        str(value["receipt_sha256"]),
    )


def _session_cache_paths(
    cache_root: str | Path,
    kind: str,
    config_sha256: str,
    spec: AuthoritativeConfirmationSessionSpec,
) -> tuple[Path, Path]:
    root = C.assert_workspace_output(cache_root)
    directory = root / kind / config_sha256 / spec.asset
    return (
        directory / f"{spec.trading_day}.json",
        directory / f"{spec.trading_day}.npz",
    )


def _empty_cache_values(
    source: Mapping[str, object],
) -> tuple[str, None, None, None, str]:
    stream_receipt = C.object_sha256({
        "schema": "QRE2CONFNOEVENT1",
        "source": source,
    })
    return "NO_NATIVE_CANDIDATES", None, None, None, stream_receipt


def cache_confirmation_feature_session(
    spec: AuthoritativeConfirmationSessionSpec,
    config: ConfirmationConfig,
    cache_root: str | Path,
) -> CachedConfirmationSession:
    source = _source_identity(spec)
    manifest_path, dataset_path = _session_cache_paths(
        cache_root, "feature_sessions", config.receipt_sha256, spec)
    if manifest_path.is_file():
        return _record_from_manifest(
            manifest_path,
            _manifest(manifest_path),
            schema=FEATURE_CACHE_SCHEMA,
            source=source,
            config_sha256=config.receipt_sha256,
        )
    candidates = read_versioned_tsv(
        spec.candidate_path, allow_empty=True)
    teachers = read_versioned_tsv(
        spec.teacher_path, allow_empty=True)
    if bool(candidates) != bool(teachers):
        raise ConfirmationRefusal(
            "candidate/teacher emptiness differs")
    if spec.event_path is None:
        if candidates or teachers or spec.source_status != "NO_EVENTS":
            raise ConfirmationRefusal(
                "absent event pack is not typed NO_EVENTS")
        status, output_path, dataset_sha, representation, stream_receipt = (
            _empty_cache_values(source)
        )
    else:
        with EventPack(spec.event_path, verify_hash=True) as pack:
            if (pack.header.asset != spec.asset
                    or pack.header.d8 != spec.trading_day
                    or pack.sidecar.get("event_pack_sha256")
                       != spec.expected_event_sha256):
                raise ConfirmationRefusal(
                    "feature cache pack identity differs")
            learnable = (
                learnable_confirmation_count(candidates, teachers)
                if candidates else 0
            )
            if learnable:
                dataset = materialize_confirmation_session(
                    pack,
                    candidates,
                    teachers,
                    config=config,
                    forecast_provider=_forecast_provider(spec),
                    prior_session_context=_prior_session_context(spec),
                    context_repository=_context_repository(spec),
                )
                dataset_sha = dataset.save(dataset_path)
                reloaded = ConfirmationDataset.load(dataset_path)
                if (reloaded.representation_sha256
                        != dataset.representation_sha256):
                    raise ConfirmationRefusal(
                        "feature cache strict reload differs")
                status = "MATERIALIZED"
                representation = dataset.representation_sha256
                output_path = str(dataset_path)
                stream_receipt = None
            else:
                stream_receipt = (
                    stream_conservation_receipt(pack).receipt_sha256)
                status = (
                    "NO_NATIVE_CANDIDATES"
                    if not candidates
                    else "NO_LEARNABLE_CANDIDATES"
                )
                representation = None
                output_path = None
                dataset_sha = None
    core = {
        "schema": FEATURE_CACHE_SCHEMA,
        "source": source,
        "config_sha256": config.receipt_sha256,
        "status": status,
        "implementation_sha256": dict(
            confirmation_implementation_hashes()),
        "dataset_path": output_path,
        "dataset_sha256": dataset_sha,
        "dataset_representation_sha256": representation,
        "empty_stream_receipt_sha256": stream_receipt,
    }
    C.atomic_json(
        manifest_path,
        {**core, "receipt_sha256": C.object_sha256(core)},
    )
    return _record_from_manifest(
        manifest_path,
        _manifest(manifest_path),
        schema=FEATURE_CACHE_SCHEMA,
        source=source,
        config_sha256=config.receipt_sha256,
    )


def cache_confirmation_opportunity_session(
    spec: AuthoritativeConfirmationSessionSpec,
    max_delay_sec: int,
    cache_root: str | Path,
) -> CachedConfirmationSession:
    config = ConfirmationConfig(
        max_delay_sec=max_delay_sec, snapshot_mode="REPLAY")
    source = _source_identity(spec)
    manifest_path, dataset_path = _session_cache_paths(
        cache_root, "opportunity_sessions", config.receipt_sha256, spec)
    if manifest_path.is_file():
        return _record_from_manifest(
            manifest_path,
            _manifest(manifest_path),
            schema=OPPORTUNITY_CACHE_SCHEMA,
            source=source,
            config_sha256=config.receipt_sha256,
        )
    candidates = read_versioned_tsv(
        spec.candidate_path, allow_empty=True)
    teachers = read_versioned_tsv(
        spec.teacher_path, allow_empty=True)
    if bool(candidates) != bool(teachers):
        raise ConfirmationRefusal(
            "candidate/teacher emptiness differs")
    if spec.event_path is None:
        if candidates or teachers or spec.source_status != "NO_EVENTS":
            raise ConfirmationRefusal(
                "absent event pack is not typed NO_EVENTS")
        status, output_path, dataset_sha, representation, stream_receipt = (
            _empty_cache_values(source)
        )
    else:
        with EventPack(spec.event_path, verify_hash=True) as pack:
            if (pack.header.asset != spec.asset
                    or pack.header.d8 != spec.trading_day
                    or pack.sidecar.get("event_pack_sha256")
                       != spec.expected_event_sha256):
                raise ConfirmationRefusal(
                    "opportunity cache pack identity differs")
            learnable = (
                learnable_confirmation_count(candidates, teachers)
                if candidates else 0
            )
            if learnable:
                dataset = materialize_confirmation_opportunity_session(
                    pack,
                    candidates,
                    teachers,
                    max_delay_sec=max_delay_sec,
                )
                dataset_sha = dataset.save(dataset_path)
                reloaded = ConfirmationOpportunitySet.load(dataset_path)
                if (reloaded.representation_sha256
                        != dataset.representation_sha256):
                    raise ConfirmationRefusal(
                        "opportunity cache strict reload differs")
                status = "MATERIALIZED"
                representation = dataset.representation_sha256
                output_path = str(dataset_path)
                stream_receipt = None
            else:
                stream_receipt = (
                    stream_conservation_receipt(pack).receipt_sha256)
                status = (
                    "NO_NATIVE_CANDIDATES"
                    if not candidates
                    else "NO_LEARNABLE_CANDIDATES"
                )
                representation = None
                output_path = None
                dataset_sha = None
    core = {
        "schema": OPPORTUNITY_CACHE_SCHEMA,
        "source": source,
        "config_sha256": config.receipt_sha256,
        "status": status,
        "implementation_sha256": dict(
            confirmation_implementation_hashes()),
        "dataset_path": output_path,
        "dataset_sha256": dataset_sha,
        "dataset_representation_sha256": representation,
        "empty_stream_receipt_sha256": stream_receipt,
    }
    C.atomic_json(
        manifest_path,
        {**core, "receipt_sha256": C.object_sha256(core)},
    )
    return _record_from_manifest(
        manifest_path,
        _manifest(manifest_path),
        schema=OPPORTUNITY_CACHE_SCHEMA,
        source=source,
        config_sha256=config.receipt_sha256,
    )


def _feature_worker(
    args: tuple[
        AuthoritativeConfirmationSessionSpec,
        ConfirmationConfig,
        str,
    ],
) -> CachedConfirmationSession:
    return cache_confirmation_feature_session(*args)


def _opportunity_worker(
    args: tuple[AuthoritativeConfirmationSessionSpec, int, str],
) -> CachedConfirmationSession:
    return cache_confirmation_opportunity_session(*args)


def materialize_feature_cache(
    specs: Sequence[AuthoritativeConfirmationSessionSpec],
    config: ConfirmationConfig,
    cache_root: str | Path,
    *,
    workers: int = 1,
) -> tuple[CachedConfirmationSession, ...]:
    return _materialize_cache(
        specs,
        _feature_worker,
        tuple((spec, config, str(cache_root)) for spec in specs),
        workers,
    )


def materialize_opportunity_cache(
    specs: Sequence[AuthoritativeConfirmationSessionSpec],
    max_delay_sec: int,
    cache_root: str | Path,
    *,
    workers: int = 1,
) -> tuple[CachedConfirmationSession, ...]:
    return _materialize_cache(
        specs,
        _opportunity_worker,
        tuple((spec, max_delay_sec, str(cache_root)) for spec in specs),
        workers,
    )


def _materialize_cache(
    specs: Sequence[AuthoritativeConfirmationSessionSpec],
    worker: object,
    arguments: Sequence[tuple[object, ...]],
    workers: int,
) -> tuple[CachedConfirmationSession, ...]:
    roster = tuple(specs)
    if (not roster
            or len({row.session for row in roster}) != len(roster)
            or not 1 <= workers <= C.MAX_CPU_WORKERS
            or len(arguments) != len(roster)):
        raise ConfirmationRefusal(
            "confirmation cache roster/workers are invalid")
    if workers == 1:
        rows = [
            worker(argument)  # type: ignore[operator]
            for argument in arguments
        ]
    else:
        rows = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pending = {
                pool.submit(worker, argument): argument
                for argument in arguments
            }
            for future in as_completed(pending):
                rows.append(future.result())
    ordered = tuple(sorted(rows, key=lambda row: row.session))
    if tuple(row.session for row in ordered) != tuple(
            sorted(spec.session for spec in roster)):
        raise ConfirmationRefusal(
            "confirmation cache result roster differs")
    return ordered


__all__ = [
    "CachedConfirmationSession",
    "cache_confirmation_feature_session",
    "cache_confirmation_opportunity_session",
    "materialize_feature_cache",
    "materialize_opportunity_cache",
]
