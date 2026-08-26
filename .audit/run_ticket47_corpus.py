#!/usr/bin/env python3
"""Build the bounded 2022-2024 Entry V2 corpus and publish its receipt."""

from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import gc
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Mapping, Sequence, cast


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORKERS = 14
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = str(WORKERS)

from engine.entry_v2 import common as C
from engine.entry_v2 import corpus_build as corpus_build_module
from engine.entry_v2 import corpus_build_assets as corpus_build_assets_module
from engine.entry_v2.confirmation import (
    CORPUS_AGE_GRID_SECONDS,
    ConfirmationDataset,
    ConfirmationConfig,
    learnable_confirmation_count,
    materialize_confirmation_session,
)
from engine.entry_v2.context_sources import (
    CausalContextRepository,
    load_context_repository,
)
from engine.entry_v2.corpus import (
    VERIFIED_SESSION_LAW_SHA256,
    _verified_session_identity,
    build_corpus,
)
from engine.entry_v2.corpus_artifacts import AssetArtifactSet
from engine.entry_v2.corpus_forecast import (
    QRE2ForecastArtifactInput,
    QRE2ForecastProvider,
)
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER, ASSET_RAW_TICK
from engine.entry_v2.discretionary_features import PriorSessionContext
from engine.entry_v2.durable_store import DurableEntryV2Store
from engine.entry_v2.event_pack import EventPack
from engine.entry_v2.session_stream import SessionArrayCache, SessionEventSource


ASSETS = ("HG", "NKD", "SI")
MINIMUM_D8_EXCLUSIVE = 20220101
MAXIMUM_D8 = 20241231
SEALED_D8 = 20250101
SOURCE_ROOT = ROOT / "artifacts/cache/port/entry_v2"
SESSION_ROOT = ROOT / "artifacts/cache/corpus_2022_2024/sessions"
CORPUS_ROOT = ROOT / "artifacts/cache/ticket47-corpus"
DURABLE_ROOT = CORPUS_ROOT / "durable"
AUDIT_ROOT = ROOT / ".audit"
RECEIPT_PATH = AUDIT_ROOT / "ticket47-corpus.json"
PROGRESS_PATH = AUDIT_ROOT / "ticket47-progress.json"
RECEIPT_SCHEMA = "QRE2TICKET47CORPUS1"
PROGRESS_SCHEMA = "QRE2TICKET47PROGRESS1"
SHARD_SCHEMA = "QRE2TICKET47SHARD1"
AGE_CONFIG = ConfirmationConfig(
    max_delay_sec=300,
    snapshot_mode="TRAINING",
    age_grid="CORPUS",
)

_CACHE_FLOOR_BYTES = 16 * 1024 * 1024
_CACHE_CAP_BYTES = 256 * 1024 * 1024
_CACHE_BYTES_PER_EVENT = 133


@dataclass(frozen=True, slots=True)
class SourceRoster:
    candidates: Mapping[str, Mapping[int, Mapping[str, str]]]
    teachers: Mapping[str, Mapping[int, Mapping[str, str]]]
    days: Mapping[str, tuple[int, ...]]

    @property
    def session_counts(self) -> dict[str, int]:
        return {asset: len(self.days[asset]) for asset in ASSETS}

    @property
    def total_sessions(self) -> int:
        return sum(self.session_counts.values())


class ProgressWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.sequence = 0

    def update(
        self,
        stage: str,
        detail: str,
        completed: int,
        total: int,
        *,
        status: str = "RUNNING",
        error: str | None = None,
    ) -> None:
        self.sequence += 1
        payload: dict[str, object] = {
            "schema": PROGRESS_SCHEMA,
            "status": status,
            "pid": os.getpid(),
            "stage": stage,
            "detail": detail,
            "completed": int(completed),
            "total": int(total),
            "sequence": self.sequence,
            "updated_epoch": time.time(),
        }
        if error is not None:
            payload["error"] = error
        _atomic_json(self.path, payload)


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json_object(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"cannot read JSON object {path}") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal(
            f"JSON payload must be an object, got {type(value).__name__} at {path}"
        )
    return value


class FrozenGridShardWriter:
    """Persist one nine-age confirmation shard receipt per bounded session."""

    def __init__(
        self,
        *,
        root: Path,
        config: ConfirmationConfig,
        forecast_provider_by_asset: Mapping[str, QRE2ForecastProvider],
        context_repository_by_asset: Mapping[str, CausalContextRepository],
    ) -> None:
        self.root = root
        self.config = config
        self.forecast_provider_by_asset = forecast_provider_by_asset
        self.context_repository_by_asset = context_repository_by_asset
        self.prior_context_by_asset: dict[str, PriorSessionContext] = {}
        self.records: dict[tuple[str, int], dict[str, object]] = {}

    def _paths(self, asset: str, d8: int) -> tuple[Path, Path]:
        session_root = self.root / self.config.receipt_sha256 / asset
        return session_root / f"{d8}.npz", session_root / f"{d8}.json"

    def _identity(
        self,
        *,
        asset: str,
        d8: int,
        event_pack_sha256: str,
        candidates: Sequence[Mapping[str, object]],
        teachers: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        forecast_provider = self.forecast_provider_by_asset.get(asset)
        context_repository = self.context_repository_by_asset.get(asset)
        prior_context = self.prior_context_by_asset.get(asset)
        return {
            "asset": asset,
            "d8": d8,
            "event_pack_sha256": event_pack_sha256,
            "candidate_rows_sha256": C.object_sha256(list(candidates)),
            "teacher_rows_sha256": C.object_sha256(list(teachers)),
            "forecast_receipt_sha256": (
                "ABSENT"
                if forecast_provider is None
                else forecast_provider.receipt_sha256
            ),
            "context_receipt_sha256": (
                "ABSENT"
                if context_repository is None
                else context_repository.receipt["receipt_sha256"]
            ),
            "prior_context_receipt_sha256": (
                "ABSENT"
                if prior_context is None
                else prior_context.receipt_sha256
            ),
            "confirmation_config_sha256": self.config.receipt_sha256,
            "age_grid_seconds": list(CORPUS_AGE_GRID_SECONDS),
        }

    def _publish_record(
        self,
        *,
        identity: Mapping[str, object],
        status: str,
        dataset: Mapping[str, object] | None,
    ) -> dict[str, object]:
        asset = str(identity["asset"])
        d8 = int(identity["d8"])
        _, manifest_path = self._paths(asset, d8)
        core: dict[str, object] = {
            "schema": SHARD_SCHEMA,
            **identity,
            "status": status,
            "dataset": dataset,
        }
        record = {**core, "receipt_sha256": C.object_sha256(core)}
        _atomic_json(manifest_path, record)
        self.records[(asset, d8)] = record
        return record

    def _load_existing(
        self, identity: Mapping[str, object]
    ) -> dict[str, object] | None:
        asset = str(identity["asset"])
        d8 = int(identity["d8"])
        _, manifest_path = self._paths(asset, d8)
        if not manifest_path.exists():
            return None
        record = dict(_read_json_object(manifest_path))
        core = dict(record)
        receipt_sha256 = str(core.pop("receipt_sha256", ""))
        if (
            core.get("schema") != SHARD_SCHEMA
            or any(core.get(key) != value for key, value in identity.items())
            or receipt_sha256 != C.object_sha256(core)
        ):
            raise C.EntryV2Refusal(
                f"ticket 47 shard receipt differs for {(asset, d8)!r}"
            )
        status = str(record.get("status", ""))
        dataset_record = record.get("dataset")
        if status == "MATERIALIZED":
            if not isinstance(dataset_record, dict):
                raise C.EntryV2Refusal(
                    f"ticket 47 shard dataset receipt is missing for {(asset, d8)!r}"
                )
            dataset_path = Path(str(dataset_record.get("path", "")))
            loaded = ConfirmationDataset.load(dataset_path)
            if (
                C.file_sha256(dataset_path) != dataset_record.get("sha256")
                or loaded.representation_sha256
                != dataset_record.get("representation_sha256")
                or len(loaded.features) != int(dataset_record.get("rows", -1))
            ):
                raise C.EntryV2Refusal(
                    f"ticket 47 shard strict reload differs for {(asset, d8)!r}"
                )
        elif status not in {"NO_NATIVE_CANDIDATES", "NO_LEARNABLE_CANDIDATES"}:
            raise C.EntryV2Refusal(
                f"ticket 47 shard status is invalid for {(asset, d8)!r}: {status!r}"
            )
        self.records[(asset, d8)] = record
        return record

    def observe_session(
        self,
        *,
        source: SessionEventSource,
        pack: EventPack,
        candidates: Sequence[Mapping[str, object]],
        teachers: Sequence[Mapping[str, object]],
    ) -> None:
        asset = source.asset
        d8 = source.d8
        event_pack_sha256 = str(
            pack.sidecar.get("event_pack_sha256")
            or pack.sidecar.get("output_sha256")
            or ""
        )
        identity = self._identity(
            asset=asset,
            d8=d8,
            event_pack_sha256=event_pack_sha256,
            candidates=candidates,
            teachers=teachers,
        )
        if self._load_existing(identity) is not None:
            return
        if type(pack).__name__ == "_VerifiedPackView":
            raise C.EntryV2Refusal(
                f"ticket 47 verified session lacks its frozen shard for {(asset, d8)!r}"
            )
        learnable = learnable_confirmation_count(
            candidates=candidates,
            teachers=teachers,
        )
        if learnable == 0:
            self._publish_record(
                identity=identity,
                status="NO_LEARNABLE_CANDIDATES",
                dataset=None,
            )
            return
        dataset = materialize_confirmation_session(
            pack,
            candidates,
            teachers,
            config=self.config,
            forecast_provider=self.forecast_provider_by_asset[asset],
            prior_session_context=self.prior_context_by_asset.get(asset),
            context_repository=self.context_repository_by_asset[asset],
        )
        dataset_path, _ = self._paths(asset, d8)
        dataset_sha256 = dataset.save(dataset_path)
        strict = ConfirmationDataset.load(dataset_path)
        if strict.representation_sha256 != dataset.representation_sha256:
            raise C.EntryV2Refusal(
                f"ticket 47 shard strict reload differs for {(asset, d8)!r}"
            )
        self._publish_record(
            identity=identity,
            status="MATERIALIZED",
            dataset={
                "path": str(dataset_path.resolve()),
                "sha256": dataset_sha256,
                "representation_sha256": strict.representation_sha256,
                "rows": len(strict.features),
                "features": len(strict.feature_names),
            },
        )

    def observe_cached_session(
        self,
        *,
        source: SessionEventSource,
        candidates: Sequence[Mapping[str, object]],
        teachers: Sequence[Mapping[str, object]],
    ) -> None:
        asset = source.asset
        d8 = source.d8
        identity = self._identity(
            asset=asset,
            d8=d8,
            event_pack_sha256=source.source_sha256,
            candidates=candidates,
            teachers=teachers,
        )
        if self._load_existing(identity) is None:
            raise C.EntryV2Refusal(
                f"ticket 47 cached session lacks its frozen shard for {(asset, d8)!r}"
            )

    def finish_session(self, state: SimpleNamespace) -> None:
        key = (str(state.asset), int(state.d8))
        if key not in self.records:
            if state.candidate_rows:
                raise C.EntryV2Refusal(
                    f"ticket 47 diagnostic observer missed candidate session {key!r}"
                )
            identity = self._identity(
                asset=key[0],
                d8=key[1],
                event_pack_sha256=str(state.event_hash),
                candidates=state.candidate_rows,
                teachers=state.teacher_rows,
            )
            if self._load_existing(identity) is None:
                self._publish_record(
                    identity=identity,
                    status="NO_NATIVE_CANDIDATES",
                    dataset=None,
                )
        self._capture_prior_context(state)

    def _capture_prior_context(self, state: SimpleNamespace) -> None:
        if (
            state.event_hash == "ABSENT"
            or state.cm.get("status") not in {"READY", "NO_ATR14"}
            or int(state.cm.get("raw_events", "0")) <= 1
            or int(state.cm.get("two_sided_events", "0")) <= 1
            or int(state.cm.get("sane_events", "0")) <= 1
        ):
            return

        def make_prior(pack: EventPack) -> PriorSessionContext:
            return PriorSessionContext(
                rows=pack.rows,
                asset=str(state.asset),
                trading_day=int(state.d8),
                event_pack_sha256=str(state.event_hash),
                raw_tick=ASSET_RAW_TICK[str(state.asset)],
                multiplier=ASSET_MULTIPLIER[str(state.asset)],
            )

        if state.verified_hit:
            with EventPack(Path(state.event_path), verify_hash=True) as full_pack:
                prior = make_prior(full_pack)
        else:
            if state.pack is None:
                raise C.EntryV2Refusal(
                    f"ticket 47 prior source is absent for {(state.asset, state.d8)!r}"
                )
            prior = make_prior(state.pack)
        self.prior_context_by_asset[str(state.asset)] = prior

    def verify_complete(
        self, roster: Sequence[tuple[str, int]]
    ) -> tuple[dict[str, int], dict[str, int], list[dict[str, object]]]:
        expected = set(roster)
        if set(self.records) != expected:
            missing = sorted(expected - set(self.records))
            extra = sorted(set(self.records) - expected)
            raise C.EntryV2Refusal(
                f"ticket 47 shard roster differs: missing={missing[:3]!r}, "
                f"extra={extra[:3]!r}"
            )
        shard_counts = {
            asset: sum(key[0] == asset for key in self.records)
            for asset in ASSETS
        }
        materialized_counts = {
            asset: sum(
                key[0] == asset and record.get("status") == "MATERIALIZED"
                for key, record in self.records.items()
            )
            for asset in ASSETS
        }
        samples: list[dict[str, object]] = []
        for asset in ASSETS:
            for year in (2022, 2023, 2024):
                choices = sorted(
                    (
                        key
                        for key, record in self.records.items()
                        if key[0] == asset
                        and key[1] // 10000 == year
                        and record.get("status") == "MATERIALIZED"
                    ),
                    key=lambda key: key[1],
                )
                if not choices:
                    raise C.EntryV2Refusal(
                        f"ticket 47 has no materialized shard for {(asset, year)!r}"
                    )
                record = self.records[choices[0]]
                dataset_record = cast(dict[str, object], record["dataset"])
                loaded = ConfirmationDataset.load(
                    Path(str(dataset_record["path"]))
                )
                samples.append(
                    {
                        "asset": asset,
                        "year": year,
                        "d8": choices[0][1],
                        "representation_sha256": loaded.representation_sha256,
                        "rows": len(loaded.features),
                    }
                )
        return shard_counts, materialized_counts, samples


def _versioned_tsv_rows(path: Path) -> tuple[dict[str, str], ...]:
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeError) as exc:
        raise C.EntryV2Refusal(f"cannot read versioned TSV {path}") from exc
    if len(lines) < 2 or not lines[0].startswith("# QRE2"):
        raise C.EntryV2Refusal(f"versioned TSV header differs at {path}")
    rows = tuple(csv.DictReader(lines[1:], delimiter="\t"))
    if any(
        None in row or any(value is None for value in row.values())
        for row in rows
    ):
        raise C.EntryV2Refusal(f"versioned TSV row width differs at {path}")
    return tuple(
        {str(key): str(value) for key, value in row.items()}
        for row in rows
    )


def _previous_d8(day: int) -> int:
    parsed = datetime.strptime(f"{int(day):08d}", "%Y%m%d")
    return int((parsed - timedelta(days=1)).strftime("%Y%m%d"))


def _session_array_cache_bytes(event_count: int) -> int:
    if event_count < 0:
        raise C.EntryV2Refusal(
            f"session array cache needs a nonnegative event count, got {event_count}"
        )
    planned = int(event_count) * _CACHE_BYTES_PER_EVENT + 1
    return min(_CACHE_CAP_BYTES, max(_CACHE_FLOOR_BYTES, planned))


def _validate_window_days(
    days: Mapping[str, Sequence[int]],
    minimum_d8_exclusive: int,
    maximum_d8: int,
) -> None:
    C.guard_date(minimum_d8_exclusive)
    C.guard_date(maximum_d8)
    if maximum_d8 >= SEALED_D8:
        raise C.EntryV2Refusal(
            f"ticket 47 maximum must stay before {SEALED_D8}, got {maximum_d8}"
        )
    for asset in ASSETS:
        selected = tuple(int(day) for day in days.get(asset, ()))
        if not selected:
            raise C.EntryV2Refusal(f"ticket 47 has no assembled days for {asset}")
        if selected != tuple(sorted(set(selected))):
            raise C.EntryV2Refusal(
                f"ticket 47 days must be unique and chronological for {asset}"
            )
        if selected[0] <= minimum_d8_exclusive or selected[-1] > maximum_d8:
            raise C.EntryV2Refusal(
                f"ticket 47 window excludes resolved days for {asset}, "
                f"first={selected[0]} last={selected[-1]} "
                f"minimum_d8_exclusive={minimum_d8_exclusive} "
                f"maximum_d8={maximum_d8}"
            )
        if any(day >= SEALED_D8 for day in selected):
            raise C.EntryV2Refusal(
                f"ticket 47 resolved a sealed day for {asset}, got {selected[-1]}"
            )


def _assembled_days(asset: str) -> tuple[int, ...]:
    directory = SESSION_ROOT / asset
    try:
        days = tuple(
            sorted(
                int(path.stem)
                for path in directory.glob("*.json")
                if path.stem.isdigit()
                and MINIMUM_D8_EXCLUSIVE < int(path.stem) <= MAXIMUM_D8
            )
        )
    except OSError as exc:
        raise C.EntryV2Refusal(
            f"cannot list assembled sessions for {asset} at {directory}"
        ) from exc
    return days


def _manifest_by_day(path: Path, asset: str) -> dict[int, Mapping[str, str]]:
    rows = _versioned_tsv_rows(path)
    by_day = {int(row["d8"]): row for row in rows}
    if len(by_day) != len(rows):
        raise C.EntryV2Refusal(f"manifest repeats a day for {asset} at {path}")
    if any(row.get("asset") != asset for row in rows):
        raise C.EntryV2Refusal(f"manifest asset differs for {asset} at {path}")
    return by_day


def _load_roster() -> SourceRoster:
    candidates: dict[str, Mapping[int, Mapping[str, str]]] = {}
    teachers: dict[str, Mapping[int, Mapping[str, str]]] = {}
    days: dict[str, tuple[int, ...]] = {}
    for asset in ASSETS:
        candidate_rows = _manifest_by_day(
            SOURCE_ROOT / f"g1/candidates/{asset}/manifest.tsv",
            asset,
        )
        teacher_rows = _manifest_by_day(
            SOURCE_ROOT / f"g1/teacher/{asset}/manifest.tsv",
            asset,
        )
        if set(candidate_rows) != set(teacher_rows):
            raise C.EntryV2Refusal(
                f"candidate and teacher manifest days differ for {asset}"
            )
        assembled = _assembled_days(asset)
        selected_manifest = tuple(
            day
            for day in sorted(candidate_rows)
            if MINIMUM_D8_EXCLUSIVE < day <= MAXIMUM_D8
        )
        missing = sorted(set(assembled) - set(selected_manifest))
        extra = sorted(set(selected_manifest) - set(assembled))
        unexpected_extra = [
            day
            for day in extra
            if (
                C.denominator_disposition(asset, day) == "INCLUDE"
                or int(candidate_rows[day]["rows"]) != 0
                or int(teacher_rows[day]["rows"]) != 0
            )
        ]
        if missing or unexpected_extra:
            raise C.EntryV2Refusal(
                f"assembled and G1 session rosters differ for {asset}, "
                f"missing={missing[:10]} unexpected_extra={unexpected_extra[:10]}"
            )
        candidates[asset] = candidate_rows
        teachers[asset] = teacher_rows
        days[asset] = assembled
    _validate_window_days(days, MINIMUM_D8_EXCLUSIVE, MAXIMUM_D8)
    first = {asset: values[0] for asset, values in days.items()}
    if set(first.values()) != {20220102}:
        raise C.EntryV2Refusal(
            f"first assembled 2022 session differs, got {first}"
        )
    if _previous_d8(min(first.values())) != MINIMUM_D8_EXCLUSIVE:
        raise C.EntryV2Refusal(
            f"minimum_d8_exclusive must be the day before {min(first.values())}, "
            f"got {MINIMUM_D8_EXCLUSIVE}"
        )
    return SourceRoster(candidates, teachers, days)


def _maximum_day_event_count(
    roster: SourceRoster,
) -> tuple[int, str, int]:
    maximum = (-1, "", -1)
    for asset in ASSETS:
        for day in roster.days[asset]:
            row = roster.candidates[asset][day]
            value = int(row["raw_events"])
            if value > maximum[0]:
                maximum = (value, asset, day)
    event_count, asset, day = maximum
    sidecar = _read_json_object(
        SOURCE_ROOT / f"events/{asset}/{day}.qre2.json"
    )
    sidecar_count = int(sidecar.get("event_count", -1))
    if (
        sidecar.get("asset") != asset
        or int(sidecar.get("d8", -1)) != day
        or sidecar_count != event_count
    ):
        raise C.EntryV2Refusal(
            f"cache sizing event sidecar differs for {asset}/{day}, "
            f"manifest={event_count} sidecar={sidecar_count}"
        )
    return event_count, asset, day


def _artifact_sets() -> tuple[AssetArtifactSet, ...]:
    return tuple(
        AssetArtifactSet(
            SOURCE_ROOT,
            asset,
            C.file_sha256(
                SOURCE_ROOT / f"g1/candidates/{asset}/manifest.tsv"
            ),
            C.file_sha256(
                SOURCE_ROOT / f"g1/teacher/{asset}/manifest.tsv"
            ),
            C.file_sha256(
                SOURCE_ROOT / f"g1/receipts/{asset}.candidates.json"
            ),
            C.file_sha256(
                SOURCE_ROOT / f"g1/receipts/{asset}.teacher.json"
            ),
        )
        for asset in ASSETS
    )


def _forecast_provider() -> QRE2ForecastProvider:
    return QRE2ForecastProvider(
        tuple(
            QRE2ForecastArtifactInput(
                SOURCE_ROOT,
                asset,
                C.file_sha256(SOURCE_ROOT / f"forecast/{asset}.qrf4.tsv"),
                C.file_sha256(SOURCE_ROOT / f"forecast/{asset}.qrf4.json"),
            )
            for asset in ASSETS
        )
    )


def _context_repositories() -> dict[str, CausalContextRepository]:
    return {
        asset: load_context_repository(asset, MAXIMUM_D8)
        for asset in ASSETS
    }


def _stage_wrapper(
    progress: ProgressWriter,
    stage: str,
    detail: str,
    completed: int,
    total: int,
    original: Callable[[SimpleNamespace], Any],
) -> Callable[[SimpleNamespace], Any]:
    def wrapped(state: SimpleNamespace) -> Any:
        progress.update(stage, detail, completed, total)
        result = original(state)
        progress.update(stage, f"{detail}_complete", completed + 1, total)
        return result

    return wrapped


@contextmanager
def _instrument_build(
    cache: SessionArrayCache,
    progress: ProgressWriter,
    total_sessions: int,
    shard_writer: FrozenGridShardWriter,
    included_sessions: frozenset[tuple[str, int]],
) -> Iterator[dict[str, int]]:
    counts = {asset: 0 for asset in ASSETS}
    replacements: list[tuple[object, str, object]] = []

    def replace(target: object, name: str, value: object) -> None:
        replacements.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    original_publish = cast(
        Callable[[SimpleNamespace], None],
        corpus_build_assets_module._publish_and_close_session,
    )

    def publish_and_record(state: SimpleNamespace) -> None:
        day = int(state.d8)
        asset = str(state.asset)
        if day >= SEALED_D8:
            raise C.EntryV2Refusal(
                f"ticket 47 opened a sealed session, got {asset}/{day}"
            )
        included = (asset, day) in included_sessions
        if included:
            shard_writer.finish_session(state)
        original_publish(state)
        cache.clear()
        if not included:
            return
        counts[asset] += 1
        completed = sum(counts.values())
        progress.update(
            "materialize",
            f"{asset}/{day}",
            completed,
            total_sessions,
        )

    replace(
        corpus_build_assets_module,
        "_publish_and_close_session",
        publish_and_record,
    )
    materialize = cast(
        Callable[[SimpleNamespace], Any],
        corpus_build_module._materialize_assets,
    )
    assemble_evidence = cast(
        Callable[[SimpleNamespace], Any],
        corpus_build_module._assemble_evidence,
    )
    assemble_sessions = cast(
        Callable[[SimpleNamespace], Any],
        corpus_build_module._assemble_sessions,
    )
    assemble_replay = cast(
        Callable[[SimpleNamespace], Any],
        corpus_build_module._assemble_replay,
    )
    finish = cast(
        Callable[[SimpleNamespace], Any],
        corpus_build_module._finish_corpus,
    )
    replace(
        corpus_build_module,
        "_materialize_assets",
        _stage_wrapper(
            progress,
            "materialize",
            "start",
            0,
            total_sessions,
            materialize,
        ),
    )
    replace(
        corpus_build_module,
        "_assemble_evidence",
        _stage_wrapper(
            progress,
            "assemble",
            "evidence",
            0,
            3,
            assemble_evidence,
        ),
    )
    replace(
        corpus_build_module,
        "_assemble_sessions",
        _stage_wrapper(
            progress,
            "assemble",
            "sessions",
            1,
            3,
            assemble_sessions,
        ),
    )
    replace(
        corpus_build_module,
        "_assemble_replay",
        _stage_wrapper(
            progress,
            "assemble",
            "replay",
            2,
            3,
            assemble_replay,
        ),
    )
    replace(
        corpus_build_module,
        "_finish_corpus",
        _stage_wrapper(
            progress,
            "publish",
            "corpus_receipt",
            0,
            1,
            finish,
        ),
    )
    try:
        yield counts
    finally:
        for target, name, original in reversed(replacements):
            setattr(target, name, original)


def _verify_products(
    store: DurableEntryV2Store,
    roster: SourceRoster,
    progress: ProgressWriter,
) -> tuple[dict[str, int], dict[str, list[dict[str, object]]]]:
    counts = {asset: 0 for asset in ASSETS}
    samples: dict[str, list[dict[str, object]]] = {
        asset: [] for asset in ASSETS
    }
    total = roster.total_sessions
    completed = 0
    for asset in ASSETS:
        sampled_years: set[int] = set()
        for day in roster.days[asset]:
            identity = _verified_session_identity(
                asset,
                day,
                roster.candidates[asset][day],
                roster.teachers[asset][day],
            )
            product = store.load(
                "verified-sessions",
                identity,
                VERIFIED_SESSION_LAW_SHA256,
            )
            if product is None:
                raise C.EntryV2Refusal(
                    f"verified ticket 47 session is absent for {asset}/{day}"
                )
            try:
                counts[asset] += 1
                year = day // 10000
                if year not in sampled_years:
                    samples[asset].append(
                        {
                            "day": day,
                            "strict_reloaded": True,
                            "key": product.key,
                            "array_count": len(product.arrays),
                            "receipt_sha256": product.receipt[
                                "receipt_sha256"
                            ],
                        }
                    )
                    sampled_years.add(year)
            finally:
                product.close()
            completed += 1
            if completed % 100 == 0 or completed == total:
                progress.update(
                    "publish",
                    "strict_reload",
                    completed,
                    total,
                )
        if sampled_years != {2022, 2023, 2024}:
            raise C.EntryV2Refusal(
                f"strict reload samples need 2022, 2023, and 2024 for {asset}, "
                f"got {sorted(sampled_years)}"
            )
    return counts, samples


def _existing_receipt() -> Mapping[str, object] | None:
    if not RECEIPT_PATH.is_file():
        return None
    value = _read_json_object(RECEIPT_PATH)
    window = value.get("window")
    expected_window = {
        "minimum_d8_exclusive": MINIMUM_D8_EXCLUSIVE,
        "maximum_d8": MAXIMUM_D8,
    }
    if (
        value.get("schema") != RECEIPT_SCHEMA
        or value.get("status") != "PASS"
        or window != expected_window
    ):
        raise C.EntryV2Refusal(
            f"existing ticket 47 receipt identity differs at {RECEIPT_PATH}"
        )
    return value


def _publish_receipt(payload: dict[str, object]) -> str:
    payload["receipt_sha256"] = C.object_sha256(payload)
    _atomic_json(RECEIPT_PATH, payload)
    stored = _read_json_object(RECEIPT_PATH)
    if stored != C.canonical_json_value(payload):
        raise C.EntryV2Refusal(
            f"ticket 47 receipt strict reload differs at {RECEIPT_PATH}"
        )
    return str(payload["receipt_sha256"])


def _selftest() -> int:
    synthetic = {asset: (20220102,) for asset in ASSETS}
    _validate_window_days(synthetic, 20220101, 20220102)
    if _previous_d8(20220102) != 20220101:
        raise AssertionError(
            f"synthetic window expected 20220101, got {_previous_d8(20220102)}"
        )
    refused_2025 = False
    try:
        _validate_window_days(
            {asset: (20250101,) for asset in ASSETS},
            20241231,
            20250101,
        )
    except C.EntryV2Refusal:
        refused_2025 = True
    if not refused_2025:
        raise AssertionError("synthetic 2025 window was not refused")
    if _session_array_cache_bytes(0) != _CACHE_FLOOR_BYTES:
        raise AssertionError(
            "cache floor selftest differs, "
            f"got {_session_array_cache_bytes(0)}"
        )
    exact_events = 481637
    exact_bytes = exact_events * _CACHE_BYTES_PER_EVENT + 1
    if _session_array_cache_bytes(exact_events) != exact_bytes:
        raise AssertionError(
            f"cache sizing selftest expected {exact_bytes}, "
            f"got {_session_array_cache_bytes(exact_events)}"
        )
    huge = _CACHE_CAP_BYTES // _CACHE_BYTES_PER_EVENT + 1
    if _session_array_cache_bytes(huge) != _CACHE_CAP_BYTES:
        raise AssertionError(
            f"cache cap selftest expected {_CACHE_CAP_BYTES}, "
            f"got {_session_array_cache_bytes(huge)}"
        )
    if AGE_CONFIG.offsets != tuple(CORPUS_AGE_GRID_SECONDS):
        raise AssertionError(
            f"ticket 47 age grid must stay frozen at nine ages, "
            f"got {AGE_CONFIG.offsets}"
        )
    with tempfile.TemporaryDirectory(
        dir=AUDIT_ROOT,
        prefix="ticket47-selftest-",
    ) as raw:
        progress_path = Path(raw) / "progress.json"
        writer = ProgressWriter(progress_path)
        writer.update("materialize", "synthetic/20220102", 1, 1)
        stored = _read_json_object(progress_path)
        if (
            stored.get("schema") != PROGRESS_SCHEMA
            or stored.get("stage") != "materialize"
            or stored.get("completed") != 1
        ):
            raise AssertionError(
                f"progress strict reload selftest differs, got {stored}"
            )
        shard_writer = FrozenGridShardWriter(
            root=Path(raw) / "shards",
            config=AGE_CONFIG,
            forecast_provider_by_asset={},
            context_repository_by_asset={},
        )
        shard_writer.observe_session(
            source=cast(
                SessionEventSource,
                SimpleNamespace(asset="HG", d8=20220102),
            ),
            pack=cast(
                EventPack,
                SimpleNamespace(
                    sidecar={"event_pack_sha256": "0" * 64}
                ),
            ),
            candidates=(),
            teachers=(),
        )
        shard_record = shard_writer.records.get(("HG", 20220102))
        if (
            shard_record is None
            or shard_record.get("schema") != SHARD_SCHEMA
            or shard_record.get("status") != "NO_LEARNABLE_CANDIDATES"
        ):
            raise AssertionError(
                f"frozen shard selftest differs, got {shard_record}"
            )
    print("selftest_ok")
    return 0


def _run() -> int:
    existing = _existing_receipt()
    if existing is not None:
        print(
            json.dumps(
                {
                    "receipt": str(RECEIPT_PATH),
                    "receipt_sha256": existing.get("receipt_sha256"),
                    "status": "ALREADY_COMPLETE",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0

    started = time.perf_counter()
    progress = ProgressWriter(PROGRESS_PATH)
    progress.update("materialize", "preflight", 0, 0)
    cache: SessionArrayCache | None = None
    try:
        roster = _load_roster()
        event_count, cache_asset, cache_day = _maximum_day_event_count(
            roster
        )
        cache_bytes = _session_array_cache_bytes(event_count)
        artifacts = _artifact_sets()
        contexts = _context_repositories()
        provider = _forecast_provider()
        CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
        store = DurableEntryV2Store(DURABLE_ROOT)
        cache = SessionArrayCache(cache_bytes, durable_store=store)
        shard_writer = FrozenGridShardWriter(
            root=CORPUS_ROOT / "confirmation-shards",
            config=AGE_CONFIG,
            forecast_provider_by_asset={
                asset: provider for asset in ASSETS
            },
            context_repository_by_asset=contexts,
        )
        progress.update(
            "materialize",
            "artifact_load_complete",
            0,
            roster.total_sessions,
        )
        build_started = time.perf_counter()
        with _instrument_build(
            cache,
            progress,
            roster.total_sessions,
            shard_writer,
            frozenset(
                (asset, day)
                for asset in ASSETS
                for day in roster.days[asset]
            ),
        ) as materialized_counts:
            corpus = build_corpus(
                artifacts,
                contexts,
                provider,
                require_assets=ASSETS,
                array_cache=cache,
                maximum_d8=MAXIMUM_D8,
                minimum_d8_exclusive=MINIMUM_D8_EXCLUSIVE,
                diagnostic_observer=shard_writer,
            )
        build_wall = time.perf_counter() - build_started
        expected_counts = roster.session_counts
        if materialized_counts != expected_counts:
            raise C.EntryV2Refusal(
                f"materialized session counts differ, "
                f"expected={expected_counts} actual={materialized_counts}"
            )

        corpus_window = dict(corpus.receipt["corpus_window"])
        if (
            int(corpus_window["maximum_d8"]) != MAXIMUM_D8
            or int(corpus_window["minimum_d8_exclusive"])
            != MINIMUM_D8_EXCLUSIVE
            or int(corpus_window["observed_end_d8"]) >= SEALED_D8
        ):
            raise C.EntryV2Refusal(
                f"build_corpus resolved the wrong window, got {corpus_window}"
            )
        manifest_window_counts = {
            str(row["asset"]): int(row["sessions"])
            for row in corpus.receipt["artifacts"]
        }
        if any(
            manifest_window_counts.get(asset, 0) < expected_counts[asset]
            for asset in ASSETS
        ):
            raise C.EntryV2Refusal(
                f"build_corpus manifest window omits assembled sessions, "
                f"expected={expected_counts} actual={manifest_window_counts}"
            )
        corpus_session_count = int(corpus.receipt["sessions"])
        if not 0 < corpus_session_count <= roster.total_sessions:
            raise C.EntryV2Refusal(
                f"build_corpus included session count is invalid, "
                f"assembled={roster.total_sessions} included={corpus_session_count}"
            )
        resolved_days = tuple(
            int(row["d8"]) for row in corpus.receipt["session_specs"]
        )
        if resolved_days and max(resolved_days) >= SEALED_D8:
            raise C.EntryV2Refusal(
                f"build_corpus session specs opened 2025, got {max(resolved_days)}"
            )
        corpus_summary = {
            "receipt_sha256": corpus.receipt["receipt_sha256"],
            "sessions": int(corpus.receipt["sessions"]),
            "candidate_batches": int(corpus.receipt["candidate_batches"]),
            "verified_session_warm_hits": int(
                corpus.receipt["verified_session_warm_hits"]
            ),
            "verified_session_cold_publishes": int(
                corpus.receipt["verified_session_cold_publishes"]
            ),
            "physical_full_pack_opens": int(
                corpus.receipt["physical_full_pack_opens"]
            ),
            "window": corpus_window,
        }
        del corpus
        gc.collect()

        verification_started = time.perf_counter()
        verified_session_counts, verified_session_samples = _verify_products(
            store,
            roster,
            progress,
        )
        roster_pairs = tuple(
            (asset, day)
            for asset in ASSETS
            for day in roster.days[asset]
        )
        shard_counts, materialized_shard_counts, samples = (
            shard_writer.verify_complete(roster_pairs)
        )
        verification_wall = time.perf_counter() - verification_started
        if shard_counts != expected_counts:
            raise C.EntryV2Refusal(
                f"frozen shard counts differ, "
                f"expected={expected_counts} actual={shard_counts}"
            )
        if verified_session_counts != expected_counts:
            raise C.EntryV2Refusal(
                f"verified session counts differ, "
                f"expected={expected_counts} actual={verified_session_counts}"
            )
        total_wall = time.perf_counter() - started
        payload: dict[str, object] = {
            "schema": RECEIPT_SCHEMA,
            "ticket": 47,
            "status": "PASS",
            "completed_epoch": time.time(),
            "workers": WORKERS,
            "path": "ORACLE",
            "r6_wired": False,
            "window": {
                "minimum_d8_exclusive": MINIMUM_D8_EXCLUSIVE,
                "maximum_d8": MAXIMUM_D8,
            },
            "resolved_2025_payloads": 0,
            "require_assets": list(ASSETS),
            "age_grid": {
                "name": "CORPUS",
                "seconds": list(AGE_CONFIG.offsets),
                "count": len(AGE_CONFIG.offsets),
                "config_sha256": AGE_CONFIG.receipt_sha256,
            },
            "session_counts": expected_counts,
            "session_count_total": roster.total_sessions,
            "shard_counts": shard_counts,
            "materialized_shard_counts": materialized_shard_counts,
            "strict_reload_samples": samples,
            "verified_session_counts": verified_session_counts,
            "verified_session_reload_samples": verified_session_samples,
            "cache": {
                "bytes": cache_bytes,
                "sizing_event_count": event_count,
                "sizing_asset": cache_asset,
                "sizing_day": cache_day,
                "floor_bytes": _CACHE_FLOOR_BYTES,
                "cap_bytes": _CACHE_CAP_BYTES,
                "bytes_per_event": _CACHE_BYTES_PER_EVENT,
            },
            "wall_seconds": {
                "build_corpus": round(build_wall, 6),
                "strict_reload": round(verification_wall, 6),
                "total": round(total_wall, 6),
            },
            "artifact_action": "REUSED_STORED_CANDIDATES_TEACHERS_EVENTS_FORECASTS",
            "durable_root": str(DURABLE_ROOT),
            "shard_root": str(
                CORPUS_ROOT / "confirmation-shards" / AGE_CONFIG.receipt_sha256
            ),
            "build_corpus": corpus_summary,
            "manifest_window_counts": manifest_window_counts,
        }
        receipt_sha256 = _publish_receipt(payload)
        progress.update(
            "publish",
            "complete",
            roster.total_sessions,
            roster.total_sessions,
            status="COMPLETE",
        )
        print(
            json.dumps(
                {
                    "receipt": str(RECEIPT_PATH),
                    "receipt_sha256": receipt_sha256,
                    "session_counts": expected_counts,
                    "status": "PASS",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except BaseException as exc:
        try:
            progress.update(
                "publish",
                "failed",
                0,
                0,
                status="FAILED",
                error=f"{type(exc).__name__}: {exc}",
            )
        except BaseException:
            pass
        raise
    finally:
        if cache is not None:
            cache.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the frozen 2022-2024 ticket 47 corpus."
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run synthetic one-day contract checks without opening session inputs.",
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    return _run()


if __name__ == "__main__":
    raise SystemExit(main())
