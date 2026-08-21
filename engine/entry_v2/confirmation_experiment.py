"""Resumable real-data experiment boundary for tabular confirmation.

This module deliberately has no alternate learner or replay implementation.
It caches the authoritative session outputs of :mod:`confirmation`, combines
them under the canonical E1r/E2r chronology, and exposes cheap diagnostics for
the same CatBoost objects later used by a full rehearsal.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score

from . import common as C
from .confirmation import (
    ConfirmationConfig, ConfirmationDataset, ConfirmationOpportunitySet,
    ConfirmationRefusal, combine_confirmation_datasets,
    confirmation_implementation_hashes,
    learnable_confirmation_count,
    materialize_confirmation_opportunity_session,
    materialize_confirmation_session, read_versioned_tsv,
    stream_conservation_receipt,
)
from .confirmation_diagnostics import (
    PolicyGridEvaluation, registered_feature_sets,
    registered_policy_grid, score_confirmation_policies,
    shuffle_confirmation_targets,
)
from .confirmation_model import (
    ConfirmationModel, ConfirmationModelConfig, ConfirmationPredictions,
    FitOnlyFeatureSelector, fit_confirmation_model,
)
from .contracts import SessionRef
from .corpus import QRE2ForecastArtifactInput, QRE2ForecastProvider
from .context_sources import CausalContextRepository, load_context_repository
from .diagnostic_inputs import fit_only_rehearsal_windows
from .event_pack import EventPack
from .discretionary_features import PriorSessionContext
from .corpus import ASSET_MULTIPLIER, ASSET_RAW_TICK


FEATURE_CACHE_SCHEMA = "QRE2CONFFEATCACHE1"
OPPORTUNITY_CACHE_SCHEMA = "QRE2CONFOPPCACHE1"
ROLE_SCHEMA = "QRE2CONFROLE1"
PREDICTIVE_SCHEMA = "QRE2CONFPREDIAG1"
LANE_REGISTRY_SCHEMA = "QRE2CONFLANES1"
THRESHOLD_RUN_SCHEMA = "QRE2CONFTHRUN1"


@dataclass(frozen=True, slots=True)
class AuthoritativeConfirmationSessionSpec:
    asset: str
    trading_day: int
    event_path: str | None
    candidate_path: str
    teacher_path: str
    source_status: str
    expected_event_sha256: str
    expected_candidate_sha256: str
    expected_teacher_sha256: str
    source_root: str
    expected_forecast_artifact_sha256: str
    expected_forecast_receipt_sha256: str
    previous_event_path: str | None
    previous_trading_day: int | None
    expected_previous_event_sha256: str

    def __post_init__(self) -> None:
        if (self.asset not in C.ASSETS
                or C.denominator_disposition(self.asset, self.trading_day)
                   != "INCLUDE"
                or self.source_status not in {
                    "READY", "NO_ATR14", "NO_LOCK", "NO_EVENTS",
                    "NO_SANE_BBO"}
                or (self.event_path is None)
                   != (self.expected_event_sha256 == "ABSENT")
                or not _sha(self.expected_candidate_sha256)
                or not _sha(self.expected_teacher_sha256)
                or (self.expected_event_sha256 != "ABSENT"
                    and not _sha(self.expected_event_sha256))):
            raise ConfirmationRefusal("authoritative confirmation spec is invalid")
        if (not self.source_root
                or not _sha(self.expected_forecast_artifact_sha256)
                or not _sha(self.expected_forecast_receipt_sha256)):
            raise ConfirmationRefusal("authoritative forecast source is invalid")
        previous_present = self.previous_event_path is not None
        if (previous_present != (self.previous_trading_day is not None)
                or previous_present
                   != (self.expected_previous_event_sha256 != "ABSENT")
                or (previous_present and (
                    int(self.previous_trading_day) >= self.trading_day
                    or not _sha(self.expected_previous_event_sha256)))):
            raise ConfirmationRefusal("authoritative previous-session source is invalid")

    @property
    def session(self) -> SessionRef:
        return SessionRef(
            self.asset, self.trading_day,
            f"{self.asset}-{self.trading_day}")


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
                or populated != (self.dataset_representation_sha256 is not None)
                or not _sha(self.receipt_sha256)):
            raise ConfirmationRefusal("cached confirmation session is malformed")


@dataclass(frozen=True, slots=True)
class ConfirmationRoleCorpus:
    role: str
    window: tuple[int, int]
    dataset: ConfirmationDataset
    expected_sessions: tuple[SessionRef, ...]
    empty_sessions: tuple[SessionRef, ...]
    session_receipts: tuple[str, ...]
    receipt_sha256: str

    def validate(self) -> None:
        self.dataset.validate()
        represented = {
            SessionRef(str(asset), int(day), f"{asset}-{int(day)}")
            for asset, day in zip(self.dataset.asset, self.dataset.day)}
        if (self.role not in {"FIT", "PLATT", "THRESHOLD", "FORWARD"}
                or self.window[0] > self.window[1]
                or not self.expected_sessions
                or tuple(sorted(self.expected_sessions)) != self.expected_sessions
                or len(self.expected_sessions) != len(set(self.expected_sessions))
                or not represented <= set(self.expected_sessions)
                or set(self.empty_sessions) & represented
                or not set(self.empty_sessions) <= set(self.expected_sessions)
                or len(self.session_receipts) != len(self.expected_sessions)
                or not _sha(self.receipt_sha256)):
            raise ConfirmationRefusal("confirmation role corpus is malformed")


@dataclass(frozen=True, slots=True)
class PredictiveDiagnostic:
    rows: int
    series: int
    goal_base_rate: float
    wall_base_rate: float
    goal_auc: float
    wall_auc: float
    goal_brier: float
    wall_brier: float
    pnl_correlation: float
    top_goal_decile_lift: float
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class FeatureThresholdResult:
    feature_set: str
    input_feature_count: int
    feature_count: int
    selector_receipt_sha256: str
    model_hash: str
    model_path: str
    fit_diagnostic: PredictiveDiagnostic
    platt_diagnostic: PredictiveDiagnostic
    threshold_diagnostic: PredictiveDiagnostic
    policy_grid: PolicyGridEvaluation
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ShuffledControlResult:
    status: str
    feature_set: str
    seed: int
    threshold_diagnostic: PredictiveDiagnostic | None
    policy_grid: PolicyGridEvaluation | None
    refusal_reason: str | None
    receipt_sha256: str

    def __post_init__(self) -> None:
        measured = self.status == "MEASURED"
        if (self.status not in {"MEASURED", "REFUSED_BY_LEARNER_CONTRACT"}
                or measured != (self.threshold_diagnostic is not None)
                or measured != (self.policy_grid is not None)
                or measured == (self.refusal_reason is not None)):
            raise ConfirmationRefusal("shuffled control result is malformed")


@dataclass(frozen=True, slots=True)
class ThresholdExperimentResult:
    status: str
    stage: str
    role_receipts: Mapping[str, str]
    feature_results: tuple[FeatureThresholdResult, ...]
    selected_feature_set: str | None
    selected_model_path: str | None
    selected_policy_receipt_sha256: str | None
    shuffled_control: ShuffledControlResult | None
    receipt_sha256: str

    def __post_init__(self) -> None:
        selected = self.status == "SELECTED"
        if (self.status not in {"SELECTED", "NO_FEASIBLE_THRESHOLD"}
                or not self.feature_results
                or selected != (self.selected_feature_set is not None)
                or selected != (self.selected_model_path is not None)
                or selected != (self.selected_policy_receipt_sha256 is not None)):
            raise ConfirmationRefusal("threshold experiment result is malformed")


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


def confirmation_lane_registry() -> Mapping[str, object]:
    """Declare the recovery lane without deleting legacy evidence."""

    core = {
        "schema": LANE_REGISTRY_SCHEMA,
        "active_lane": "TABULAR_CATBOOST_CONFIRMATION_V1",
        "executable_learners": ("CATBOOST_TABULAR",),
        "active_inputs": (
            "LOSSLESS_MBP1_EVENT_STREAM", "CAUSAL_STATE_FEATURES",
            "REANCHORED_TIMESTAMP_LABELS"),
        "active_horizon_seconds": (300,),
        "legacy_lanes": ({
            "name": "ENTRY_V2_NEURAL_ARM_MATRIX",
            "status": "HISTORICAL_NON_EXECUTABLE_IN_CONFIRMATION_LANE",
            "artifacts_preserved": True,
        },),
        "transformers_registered": False,
    }
    return MappingProxyType({**core, "receipt_sha256": C.object_sha256(core)})


def discover_authoritative_session_specs(
    source_root: str | Path, window: tuple[int, int],
) -> tuple[AuthoritativeConfirmationSessionSpec, ...]:
    """Resolve exact event/candidate/teacher set algebra for one role."""

    root = Path(source_root).resolve()
    lower, upper = map(int, window)
    if lower > upper or upper >= C.HOLDOUT_START_D8:
        raise ConfirmationRefusal("confirmation discovery window is invalid/sealed")

    def rows(path: Path, schema: str) -> tuple[Mapping[str, str], ...]:
        try:
            lines = path.read_text().splitlines()
        except (OSError, UnicodeError) as exc:
            raise ConfirmationRefusal(f"cannot read authority manifest: {path}") from exc
        if not lines or not lines[0].startswith(f"# {schema} ") or len(lines) < 2:
            raise ConfirmationRefusal("authority manifest header differs")
        columns = tuple(lines[1].split("\t"))
        parsed = []
        for line in lines[2:]:
            values = tuple(line.split("\t"))
            if len(values) != len(columns):
                raise ConfirmationRefusal("authority manifest row width differs")
            parsed.append(MappingProxyType(dict(zip(columns, values))))
        return tuple(parsed)

    output = []
    for asset in C.ASSETS:
        forecast_artifact = root / "forecast" / f"{asset}.qrf4.tsv"
        forecast_receipt = root / "forecast" / f"{asset}.qrf4.json"
        if not forecast_artifact.is_file() or not forecast_receipt.is_file():
            raise ConfirmationRefusal("authoritative forward-vol artifact is absent")
        forecast_artifact_sha = C.file_sha256(forecast_artifact)
        forecast_receipt_sha = C.file_sha256(forecast_receipt)
        candidate_rows = rows(
            root / "g1/candidates" / asset / "manifest.tsv",
            "QRE2G1CANDMAN2")
        teacher_rows = rows(
            root / "g1/teacher" / asset / "manifest.tsv",
            "QRE2G1TEACHMAN2")
        candidates = {int(row["d8"]): row for row in candidate_rows}
        teachers = {int(row["d8"]): row for row in teacher_rows}
        if (len(candidates) != len(candidate_rows)
                or len(teachers) != len(teacher_rows)
                or set(candidates) != set(teachers)):
            raise ConfirmationRefusal("candidate/teacher manifest rosters differ")
        previous_by_day: dict[int, int | None] = {}
        last_present: int | None = None
        for roster_day in sorted(candidates):
            previous_by_day[roster_day] = last_present
            # A one-row holiday/reset pack is physically present but is not a
            # prior auction.  Prior memory advances only on sessions whose G1
            # authority says the BBO was usable; NO_ATR14 still has a valid
            # completed market session and is therefore eligible.
            if (candidates[roster_day]["event_pack_sha256"] != "ABSENT"
                    and candidates[roster_day]["status"]
                    in {"READY", "NO_ATR14"}
                    and int(candidates[roster_day]["raw_events"]) > 1
                    and int(candidates[roster_day]["two_sided_events"]) > 1
                    and int(candidates[roster_day]["sane_events"]) > 1):
                last_present = roster_day
        for day in sorted(candidates):
            if not lower <= day <= upper:
                continue
            disposition = C.denominator_disposition(asset, day)
            if disposition != "INCLUDE":
                continue
            candidate = candidates[day]; teacher = teachers[day]
            if (candidate["asset"] != asset or teacher["asset"] != asset
                    or int(teacher["d8"]) != day
                    or candidate["candidate_sha256"]
                       != teacher["candidate_sha256"]
                    or int(candidate["rows"]) != int(teacher["rows"])
                    or int(teacher["ready"]) + int(teacher["refused"])
                       != int(teacher["rows"])):
                raise ConfirmationRefusal("candidate/teacher authority rows differ")
            event_hash = candidate["event_pack_sha256"]
            if ((event_hash == "ABSENT")
                    != (candidate["status"] in {"NO_LOCK", "NO_EVENTS"})
                    or (event_hash == "ABSENT" and int(candidate["rows"]) != 0)):
                raise ConfirmationRefusal("candidate event/status authority differs")
            candidate_path = (root / candidate["candidate_file"]).resolve()
            teacher_path = (root / teacher["teacher_file"]).resolve()
            event_path = (None if event_hash == "ABSENT" else
                          str((root / f"events/{asset}/{day}.qre2").resolve()))
            previous_day = previous_by_day[day]
            previous_hash = ("ABSENT" if previous_day is None else
                             candidates[previous_day]["event_pack_sha256"])
            previous_path = (None if previous_day is None else str(
                (root / f"events/{asset}/{previous_day}.qre2").resolve()))
            spec = AuthoritativeConfirmationSessionSpec(
                asset, day, event_path, str(candidate_path), str(teacher_path),
                candidate["status"], event_hash,
                candidate["candidate_sha256"], teacher["teacher_sha256"],
                str(root.resolve()), forecast_artifact_sha,
                forecast_receipt_sha, previous_path, previous_day,
                previous_hash)
            # Payload pins are checked before the roster is allowed to escape
            # discovery; the cache repeats this at its own trust boundary.
            if (C.file_sha256(candidate_path) != spec.expected_candidate_sha256
                    or C.file_sha256(teacher_path) != spec.expected_teacher_sha256
                    or (event_path is not None
                        and not Path(event_path).is_file())):
                raise ConfirmationRefusal("authority manifest payload pin differs")
            output.append(spec)
    if not output:
        raise ConfirmationRefusal("authoritative confirmation role is empty")
    return tuple(sorted(output, key=lambda row: row.session))


def canonical_stage_specs(
    stage: str, source_root: str | Path,
    *, roles: Sequence[str] = ("FIT", "PLATT", "THRESHOLD"),
) -> Mapping[str, tuple[AuthoritativeConfirmationSessionSpec, ...]]:
    windows = fit_only_rehearsal_windows(stage)
    requested = tuple(str(role).upper() for role in roles)
    if not requested or len(set(requested)) != len(requested):
        raise ConfirmationRefusal("confirmation role request is empty/duplicated")
    unknown = set(requested) - set(windows)
    if unknown:
        raise ConfirmationRefusal(f"unknown confirmation roles: {sorted(unknown)}")
    return MappingProxyType({
        role: discover_authoritative_session_specs(source_root, windows[role])
        for role in requested})


def _source_identity(spec: AuthoritativeConfirmationSessionSpec) -> dict[str, object]:
    # Present packs are hashed once by EventPack(verify_hash=True) on a cold
    # materialization.  The manifest pin remains the source identity on warm
    # cache reads; re-hashing multi-GB role rosters at every startup would add
    # no protection to the already immutable cached representation receipt.
    event_sha = spec.expected_event_sha256
    candidate_sha = C.file_sha256(spec.candidate_path)
    teacher_sha = C.file_sha256(spec.teacher_path)
    forecast_artifact_sha = C.file_sha256(
        Path(spec.source_root) / "forecast" / f"{spec.asset}.qrf4.tsv")
    forecast_receipt_sha = C.file_sha256(
        Path(spec.source_root) / "forecast" / f"{spec.asset}.qrf4.json")
    previous_sha = ("ABSENT" if spec.previous_event_path is None else
                    C.file_sha256(spec.previous_event_path))
    context_receipt_sha = str(
        _context_repository(spec).receipt.get("receipt_sha256", ""))
    if not _sha(context_receipt_sha):
        raise ConfirmationRefusal("authoritative context receipt is invalid")
    if (event_sha != spec.expected_event_sha256
            or candidate_sha != spec.expected_candidate_sha256
            or teacher_sha != spec.expected_teacher_sha256
            or forecast_artifact_sha
               != spec.expected_forecast_artifact_sha256
            or forecast_receipt_sha
               != spec.expected_forecast_receipt_sha256
            or previous_sha != spec.expected_previous_event_sha256):
        raise ConfirmationRefusal("confirmation source changed after discovery")
    return {
        "asset": spec.asset, "trading_day": spec.trading_day,
        "source_status": spec.source_status,
        "event_path": spec.event_path,
        "candidate_path": spec.candidate_path,
        "teacher_path": spec.teacher_path,
        "event_sha256": event_sha,
        "candidate_sha256": candidate_sha,
        "teacher_sha256": teacher_sha,
        "forecast_artifact_sha256": forecast_artifact_sha,
        "forecast_receipt_sha256": forecast_receipt_sha,
        "previous_event_path": spec.previous_event_path,
        "previous_trading_day": spec.previous_trading_day,
        "previous_event_sha256": previous_sha,
        "context_receipt_sha256": context_receipt_sha,
    }


_FORECAST_PROVIDER_CACHE: dict[tuple[str, str, str, str], QRE2ForecastProvider] = {}
_CONTEXT_REPOSITORY_CACHE: dict[str, CausalContextRepository] = {}


def _context_repository(
    spec: AuthoritativeConfirmationSessionSpec,
) -> CausalContextRepository:
    repository = _CONTEXT_REPOSITORY_CACHE.get(spec.asset)
    if repository is None:
        repository = load_context_repository(spec.asset, C.DEVELOPMENT_END_D8)
        _CONTEXT_REPOSITORY_CACHE[spec.asset] = repository
    return repository


def _forecast_provider(
    spec: AuthoritativeConfirmationSessionSpec,
) -> QRE2ForecastProvider:
    key = (spec.source_root, spec.asset,
           spec.expected_forecast_artifact_sha256,
           spec.expected_forecast_receipt_sha256)
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
            raise ConfirmationRefusal("previous event pack identity differs")
        return PriorSessionContext(
            rows=np.asarray(pack.rows), asset=spec.asset,
            trading_day=int(spec.previous_trading_day),
            event_pack_sha256=spec.expected_previous_event_sha256,
            raw_tick=int(ASSET_RAW_TICK[spec.asset]),
            multiplier=int(ASSET_MULTIPLIER[spec.asset]))


def _manifest(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfirmationRefusal(f"cannot read confirmation cache: {path}") from exc
    if not isinstance(value, dict):
        raise ConfirmationRefusal("confirmation cache manifest is not an object")
    return value


def _record_from_manifest(
    path: Path, value: Mapping[str, object], *, schema: str,
    source: Mapping[str, object], config_sha256: str,
) -> CachedConfirmationSession:
    core = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if (value.get("schema") != schema or value.get("source") != source
            or value.get("config_sha256") != config_sha256
            or value.get("implementation_sha256")
               != dict(confirmation_implementation_hashes())
            or value.get("receipt_sha256") != C.object_sha256(core)):
        raise ConfirmationRefusal("confirmation cache identity/receipt differs")
    status = str(value.get("status"))
    session = SessionRef(str(source["asset"]), int(source["trading_day"]),
                         f"{source['asset']}-{source['trading_day']}")
    dataset_path = value.get("dataset_path")
    representation = value.get("dataset_representation_sha256")
    if status == "MATERIALIZED":
        if not isinstance(dataset_path, str) or not _sha(representation):
            raise ConfirmationRefusal("materialized cache manifest is incomplete")
        if schema == FEATURE_CACHE_SCHEMA:
            dataset = ConfirmationDataset.load(dataset_path)
        else:
            dataset = ConfirmationOpportunitySet.load(dataset_path)
        if (dataset.representation_sha256 != representation
                or C.file_sha256(dataset_path) != value.get("dataset_sha256")
                or set(np.asarray(dataset.asset, str)) != {session.asset}
                or set(np.asarray(dataset.day, np.int64)) != {session.trading_day}):
            raise ConfirmationRefusal("cached confirmation dataset differs")
    elif status in {"NO_NATIVE_CANDIDATES", "NO_LEARNABLE_CANDIDATES"}:
        if dataset_path is not None or representation is not None:
            raise ConfirmationRefusal("empty cache manifest names a dataset")
    else:
        raise ConfirmationRefusal("confirmation cache has an unknown status")
    return CachedConfirmationSession(
        session, status, str(path), dataset_path, representation,
        str(value["receipt_sha256"]))


def _session_cache_paths(
    cache_root: str | Path, kind: str, config_sha256: str,
    spec: AuthoritativeConfirmationSessionSpec,
) -> tuple[Path, Path]:
    root = C.assert_workspace_output(cache_root)
    directory = root / kind / config_sha256 / spec.asset
    return directory / f"{spec.trading_day}.json", directory / f"{spec.trading_day}.npz"


def cache_confirmation_feature_session(
    spec: AuthoritativeConfirmationSessionSpec, config: ConfirmationConfig,
    cache_root: str | Path,
) -> CachedConfirmationSession:
    source = _source_identity(spec)
    manifest_path, dataset_path = _session_cache_paths(
        cache_root, "feature_sessions", config.receipt_sha256, spec)
    if manifest_path.is_file():
        return _record_from_manifest(
            manifest_path, _manifest(manifest_path), schema=FEATURE_CACHE_SCHEMA,
            source=source, config_sha256=config.receipt_sha256)
    candidates = read_versioned_tsv(spec.candidate_path, allow_empty=True)
    teachers = read_versioned_tsv(spec.teacher_path, allow_empty=True)
    if bool(candidates) != bool(teachers):
        raise ConfirmationRefusal("candidate/teacher emptiness differs")
    if spec.event_path is None:
        if candidates or teachers or spec.source_status != "NO_EVENTS":
            raise ConfirmationRefusal("absent event pack is not typed NO_EVENTS")
        status = "NO_NATIVE_CANDIDATES"; representation = None
        output_path = None; dataset_sha = None
        stream_receipt = C.object_sha256({
            "schema": "QRE2CONFNOEVENT1", "source": source})
    else:
      with EventPack(spec.event_path, verify_hash=True) as pack:
          if (pack.header.asset != spec.asset or pack.header.d8 != spec.trading_day
                  or pack.sidecar.get("event_pack_sha256")
                     != spec.expected_event_sha256):
              raise ConfirmationRefusal("feature cache pack identity differs")
          learnable = (learnable_confirmation_count(candidates, teachers)
                       if candidates else 0)
          if learnable:
              dataset = materialize_confirmation_session(
                  pack, candidates, teachers, config=config,
                  forecast_provider=_forecast_provider(spec),
                  prior_session_context=_prior_session_context(spec),
                  context_repository=_context_repository(spec))
              dataset_sha = dataset.save(dataset_path)
              reloaded = ConfirmationDataset.load(dataset_path)
              if reloaded.representation_sha256 != dataset.representation_sha256:
                  raise ConfirmationRefusal("feature cache strict reload differs")
              status = "MATERIALIZED"
              representation = dataset.representation_sha256
              output_path = str(dataset_path)
              stream_receipt = None
          else:
              stream_receipt = stream_conservation_receipt(pack).receipt_sha256
              status = ("NO_NATIVE_CANDIDATES" if not candidates else
                        "NO_LEARNABLE_CANDIDATES")
              representation = None
              output_path = None; dataset_sha = None
    core = {
        "schema": FEATURE_CACHE_SCHEMA, "source": source,
        "config_sha256": config.receipt_sha256, "status": status,
        "implementation_sha256": dict(confirmation_implementation_hashes()),
        "dataset_path": output_path, "dataset_sha256": dataset_sha,
        "dataset_representation_sha256": representation,
        "empty_stream_receipt_sha256": stream_receipt,
    }
    C.atomic_json(manifest_path, {**core, "receipt_sha256": C.object_sha256(core)})
    return _record_from_manifest(
        manifest_path, _manifest(manifest_path), schema=FEATURE_CACHE_SCHEMA,
        source=source, config_sha256=config.receipt_sha256)


def cache_confirmation_opportunity_session(
    spec: AuthoritativeConfirmationSessionSpec, max_delay_sec: int,
    cache_root: str | Path,
) -> CachedConfirmationSession:
    config = ConfirmationConfig(
        max_delay_sec=max_delay_sec, snapshot_mode="REPLAY")
    source = _source_identity(spec)
    manifest_path, dataset_path = _session_cache_paths(
        cache_root, "opportunity_sessions", config.receipt_sha256, spec)
    if manifest_path.is_file():
        return _record_from_manifest(
            manifest_path, _manifest(manifest_path),
            schema=OPPORTUNITY_CACHE_SCHEMA, source=source,
            config_sha256=config.receipt_sha256)
    candidates = read_versioned_tsv(spec.candidate_path, allow_empty=True)
    teachers = read_versioned_tsv(spec.teacher_path, allow_empty=True)
    if bool(candidates) != bool(teachers):
        raise ConfirmationRefusal("candidate/teacher emptiness differs")
    if spec.event_path is None:
        if candidates or teachers or spec.source_status != "NO_EVENTS":
            raise ConfirmationRefusal("absent event pack is not typed NO_EVENTS")
        status = "NO_NATIVE_CANDIDATES"; representation = None
        output_path = None; dataset_sha = None
        stream_receipt = C.object_sha256({
            "schema": "QRE2CONFNOEVENT1", "source": source})
    else:
      with EventPack(spec.event_path, verify_hash=True) as pack:
          if (pack.header.asset != spec.asset or pack.header.d8 != spec.trading_day
                  or pack.sidecar.get("event_pack_sha256")
                     != spec.expected_event_sha256):
              raise ConfirmationRefusal("opportunity cache pack identity differs")
          learnable = (learnable_confirmation_count(candidates, teachers)
                       if candidates else 0)
          if learnable:
              dataset = materialize_confirmation_opportunity_session(
                  pack, candidates, teachers, max_delay_sec=max_delay_sec)
              dataset_sha = dataset.save(dataset_path)
              reloaded = ConfirmationOpportunitySet.load(dataset_path)
              if reloaded.representation_sha256 != dataset.representation_sha256:
                  raise ConfirmationRefusal("opportunity cache strict reload differs")
              status = "MATERIALIZED"
              representation = dataset.representation_sha256
              output_path = str(dataset_path)
              stream_receipt = None
          else:
              stream_receipt = stream_conservation_receipt(pack).receipt_sha256
              status = ("NO_NATIVE_CANDIDATES" if not candidates else
                        "NO_LEARNABLE_CANDIDATES")
              representation = None
              output_path = None; dataset_sha = None
    core = {
        "schema": OPPORTUNITY_CACHE_SCHEMA, "source": source,
        "config_sha256": config.receipt_sha256, "status": status,
        "implementation_sha256": dict(confirmation_implementation_hashes()),
        "dataset_path": output_path, "dataset_sha256": dataset_sha,
        "dataset_representation_sha256": representation,
        "empty_stream_receipt_sha256": stream_receipt,
    }
    C.atomic_json(manifest_path, {**core, "receipt_sha256": C.object_sha256(core)})
    return _record_from_manifest(
        manifest_path, _manifest(manifest_path),
        schema=OPPORTUNITY_CACHE_SCHEMA, source=source,
        config_sha256=config.receipt_sha256)


def _feature_worker(args: tuple[AuthoritativeConfirmationSessionSpec, ConfirmationConfig, str]
                    ) -> CachedConfirmationSession:
    return cache_confirmation_feature_session(*args)


def _opportunity_worker(args: tuple[AuthoritativeConfirmationSessionSpec, int, str]
                        ) -> CachedConfirmationSession:
    return cache_confirmation_opportunity_session(*args)


def materialize_feature_cache(
    specs: Sequence[AuthoritativeConfirmationSessionSpec], config: ConfirmationConfig,
    cache_root: str | Path, *, workers: int = 1,
) -> tuple[CachedConfirmationSession, ...]:
    return _materialize_cache(
        specs, _feature_worker,
        tuple((spec, config, str(cache_root)) for spec in specs), workers)


def materialize_opportunity_cache(
    specs: Sequence[AuthoritativeConfirmationSessionSpec], max_delay_sec: int,
    cache_root: str | Path, *, workers: int = 1,
) -> tuple[CachedConfirmationSession, ...]:
    return _materialize_cache(
        specs, _opportunity_worker,
        tuple((spec, max_delay_sec, str(cache_root)) for spec in specs), workers)


def _materialize_cache(
    specs: Sequence[AuthoritativeConfirmationSessionSpec], worker: object,
    arguments: Sequence[tuple[object, ...]], workers: int,
) -> tuple[CachedConfirmationSession, ...]:
    roster = tuple(specs)
    if (not roster or len({row.session for row in roster}) != len(roster)
            or not 1 <= workers <= C.MAX_CPU_WORKERS
            or len(arguments) != len(roster)):
        raise ConfirmationRefusal("confirmation cache roster/workers are invalid")
    if workers == 1:
        rows = [worker(argument) for argument in arguments]  # type: ignore[operator]
    else:
        rows = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pending = {pool.submit(worker, argument): argument for argument in arguments}
            for future in as_completed(pending):
                rows.append(future.result())
    ordered = tuple(sorted(rows, key=lambda row: row.session))
    if tuple(row.session for row in ordered) != tuple(
            sorted(spec.session for spec in roster)):
        raise ConfirmationRefusal("confirmation cache result roster differs")
    return ordered


def combine_feature_role(
    role: str, window: tuple[int, int],
    records: Sequence[CachedConfirmationSession],
) -> ConfirmationRoleCorpus:
    rows = tuple(sorted(records, key=lambda row: row.session))
    datasets = [ConfirmationDataset.load(row.dataset_path) for row in rows
                if row.status == "MATERIALIZED" and row.dataset_path is not None]
    if not datasets:
        raise ConfirmationRefusal("confirmation role has no candidate rows")
    combined = combine_confirmation_datasets(datasets)
    expected = tuple(row.session for row in rows)
    empty = tuple(row.session for row in rows
                  if row.status in {
                      "NO_NATIVE_CANDIDATES", "NO_LEARNABLE_CANDIDATES"})
    core = {
        "schema": ROLE_SCHEMA, "role": role, "window": window,
        "expected_sessions": tuple(asdict(row) for row in expected),
        "empty_sessions": tuple(asdict(row) for row in empty),
        "session_receipts": tuple(row.receipt_sha256 for row in rows),
        "dataset": combined.representation_sha256,
    }
    result = ConfirmationRoleCorpus(
        role, tuple(map(int, window)), combined, expected, empty,
        tuple(row.receipt_sha256 for row in rows), C.object_sha256(core))
    result.validate(); return result


def load_opportunity_shards(
    records: Sequence[CachedConfirmationSession],
) -> tuple[ConfirmationOpportunitySet, ...]:
    rows = tuple(sorted(records, key=lambda row: row.session))
    shards = tuple(ConfirmationOpportunitySet.load(row.dataset_path)
                   for row in rows if row.status == "MATERIALIZED"
                   and row.dataset_path is not None)
    if not shards:
        raise ConfirmationRefusal("opportunity cache has no materialized shards")
    return shards


def project_feature_set(
    dataset: ConfirmationDataset, feature_set: str,
) -> ConfirmationDataset:
    masks = registered_feature_sets(dataset.feature_names)
    try:
        mask = masks[str(feature_set).upper()]
    except KeyError as exc:
        raise ConfirmationRefusal("unknown registered confirmation feature set") from exc
    return dataset if bool(np.all(mask)) else dataset.select_features(mask)


def _series_weights(dataset: ConfirmationDataset) -> np.ndarray:
    _, inverse, counts = np.unique(
        np.asarray(dataset.series_id, str), return_inverse=True,
        return_counts=True)
    weights = 1.0 / counts[inverse].astype(np.float64)
    return weights * (len(weights) / weights.sum())


def _weighted_correlation(
    left: np.ndarray, right: np.ndarray, weight: np.ndarray,
) -> float:
    x = np.asarray(left, np.float64); y = np.asarray(right, np.float64)
    w = np.asarray(weight, np.float64); w = w / w.sum()
    dx = x - np.sum(w * x); dy = y - np.sum(w * y)
    denominator = math.sqrt(float(np.sum(w * dx * dx) * np.sum(w * dy * dy)))
    return 0.0 if denominator == 0 else float(np.sum(w * dx * dy) / denominator)


def predictive_diagnostic(
    dataset: ConfirmationDataset, predictions: ConfirmationPredictions,
) -> PredictiveDiagnostic:
    dataset.validate(); predictions.validate(dataset.opportunity_id)
    weights = _series_weights(dataset)
    goal = np.asarray(dataset.cert_close_usd >= C.MIN_EXPECTANCY_USD, np.int8)
    wall = np.asarray(dataset.wall_hit, np.int8)
    if len(np.unique(goal)) != 2 or len(np.unique(wall)) != 2:
        raise ConfirmationRefusal("predictive diagnostic block is one-class")
    goal_rate = float(np.average(goal, weights=weights))
    wall_rate = float(np.average(wall, weights=weights))
    threshold = float(np.quantile(predictions.goal_probability, .90))
    top = np.asarray(predictions.goal_probability) >= threshold
    top_rate = float(np.average(goal[top], weights=weights[top]))
    core = {
        "schema": PREDICTIVE_SCHEMA,
        "dataset": dataset.representation_sha256,
        "model": predictions.model_hash,
        "rows": len(goal), "series": len(set(dataset.series_id)),
        "goal_base_rate": goal_rate, "wall_base_rate": wall_rate,
        "goal_auc": float(roc_auc_score(
            goal, predictions.goal_probability, sample_weight=weights)),
        "wall_auc": float(roc_auc_score(
            wall, predictions.wall_probability, sample_weight=weights)),
        "goal_brier": float(brier_score_loss(
            goal, predictions.goal_probability, sample_weight=weights)),
        "wall_brier": float(brier_score_loss(
            wall, predictions.wall_probability, sample_weight=weights)),
        "pnl_correlation": _weighted_correlation(
            predictions.expected_pnl_usd, dataset.cert_close_usd, weights),
        "top_goal_decile_lift": top_rate / goal_rate,
    }
    return PredictiveDiagnostic(
        rows=int(core["rows"]), series=int(core["series"]),
        goal_base_rate=goal_rate, wall_base_rate=wall_rate,
        goal_auc=float(core["goal_auc"]), wall_auc=float(core["wall_auc"]),
        goal_brier=float(core["goal_brier"]), wall_brier=float(core["wall_brier"]),
        pnl_correlation=float(core["pnl_correlation"]),
        top_goal_decile_lift=float(core["top_goal_decile_lift"]),
        receipt_sha256=C.object_sha256(core))


def _load_or_fit_model(
    fit: ConfirmationDataset, platt: ConfirmationDataset,
    config: ConfirmationModelConfig, model_path: Path,
) -> ConfirmationModel:
    if model_path.exists():
        if not (model_path / "manifest.json").is_file():
            raise ConfirmationRefusal(
                f"incomplete confirmation model boundary: {model_path}")
        model = ConfirmationModel.load(model_path)
        if (model.config != config or model.feature_names != fit.feature_names
                or model.fit_representation_sha256 != fit.representation_sha256
                or model.platt_representation_sha256
                   != platt.representation_sha256):
            raise ConfirmationRefusal("cached confirmation model identity differs")
        return model
    model = fit_confirmation_model(fit, platt, config=config)
    model.save(model_path)
    loaded = ConfirmationModel.load(model_path)
    before = model.predict(platt); after = loaded.predict(platt)
    for name in ("expected_pnl_usd", "pnl_q20_usd", "goal_probability",
                 "wall_probability", "mae_q90_usd"):
        if not np.array_equal(getattr(before, name), getattr(after, name)):
            raise ConfirmationRefusal(
                f"strict model reload prediction differs: {name}")
    return loaded


def _load_or_fit_selector(
    fit: ConfirmationDataset, selector_path: Path,
) -> FitOnlyFeatureSelector:
    expected = FitOnlyFeatureSelector.fit(fit)
    if selector_path.is_file():
        loaded = FitOnlyFeatureSelector.load(selector_path)
        if loaded != expected:
            raise ConfirmationRefusal("cached fit-only selector identity differs")
        return loaded
    expected.save(selector_path)
    loaded = FitOnlyFeatureSelector.load(selector_path)
    if loaded != expected:
        raise ConfirmationRefusal("strict fit-only selector reload differs")
    return loaded


def _feature_threshold_result(
    feature_set: str, fit: ConfirmationDataset,
    platt: ConfirmationDataset, threshold: ConfirmationDataset,
    expected_threshold_sessions: Sequence[SessionRef],
    config: ConfirmationModelConfig, model_path: Path,
) -> FeatureThresholdResult:
    input_feature_count = len(fit.feature_names)
    selector = _load_or_fit_selector(
        fit, model_path.with_name(model_path.name + ".selector.json"))
    fit = selector.transform(fit)
    platt = selector.transform(platt)
    threshold = selector.transform(threshold)
    model = _load_or_fit_model(fit, platt, config, model_path)
    fit_prediction = model.predict(fit)
    platt_prediction = model.predict(platt)
    threshold_prediction = model.predict(threshold)
    fit_diag = predictive_diagnostic(fit, fit_prediction)
    platt_diag = predictive_diagnostic(platt, platt_prediction)
    threshold_diag = predictive_diagnostic(threshold, threshold_prediction)
    grid = score_confirmation_policies(
        threshold, threshold_prediction,
        expected_sessions=expected_threshold_sessions)
    core = {
        "schema": THRESHOLD_RUN_SCHEMA, "feature_set": feature_set,
        "input_feature_count": input_feature_count,
        "feature_count": len(fit.feature_names),
        "selector_receipt_sha256": selector.receipt_sha256,
        "model": model.model_hash,
        "model_path": str(model_path), "fit": fit_diag.receipt_sha256,
        "platt": platt_diag.receipt_sha256,
        "threshold": threshold_diag.receipt_sha256,
        "policy_grid": grid.receipt_sha256,
    }
    return FeatureThresholdResult(
        feature_set, input_feature_count, len(fit.feature_names),
        selector.receipt_sha256, model.model_hash,
        str(model_path), fit_diag, platt_diag, threshold_diag, grid,
        C.object_sha256(core))


def run_threshold_experiment(
    roles: Mapping[str, ConfirmationRoleCorpus],
    *, feature_sets: Sequence[str], model_config: ConfirmationModelConfig,
    output_directory: str | Path, stage: str,
    run_shuffled_control: bool = True, shuffled_seed: int = 20260819,
    model_directory: str | Path | None = None,
) -> ThresholdExperimentResult:
    """Fit/calibrate/threshold tabular variants; never opens FORWARD data."""

    if set(roles) != {"FIT", "PLATT", "THRESHOLD"}:
        raise ConfirmationRefusal("threshold experiment role roster differs")
    for corpus in roles.values():
        corpus.validate()
    if not (roles["FIT"].window[1] < roles["PLATT"].window[0]
            <= roles["PLATT"].window[1] < roles["THRESHOLD"].window[0]):
        raise ConfirmationRefusal("threshold experiment chronology differs")
    requested = tuple(str(name).upper() for name in feature_sets)
    if not requested or len(set(requested)) != len(requested):
        raise ConfirmationRefusal("feature experiment roster is empty/duplicated")
    registered = registered_feature_sets(roles["FIT"].dataset.feature_names)
    if set(requested) - set(registered):
        raise ConfirmationRefusal("feature experiment names are unregistered")

    output = C.assert_workspace_output(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    models_root = (output / "models" if model_directory is None else
                   C.assert_workspace_output(model_directory))
    policy_grid_receipt = C.object_sha256(tuple(
        row.receipt_sha256 for row in registered_policy_grid(
            roles["THRESHOLD"].dataset.max_delay_sec)))
    role_receipts = {name: roles[name].receipt_sha256
                     for name in ("FIT", "PLATT", "THRESHOLD")}
    identity = {
        "schema": THRESHOLD_RUN_SCHEMA, "stage": str(stage).upper(),
        "role_receipts": role_receipts, "feature_sets": requested,
        "model_config": asdict(model_config),
        "model_directory": str(models_root),
        "policy_grid_receipt_sha256": policy_grid_receipt,
        "lane_registry": confirmation_lane_registry(),
        "forward_opened": False,
    }
    identity_path = output / "identity.json"
    if identity_path.is_file():
        if _manifest(identity_path) != identity:
            raise ConfirmationRefusal("threshold experiment restart identity differs")
    else:
        C.atomic_json(identity_path, identity)

    results = []
    for name in requested:
        fit = project_feature_set(roles["FIT"].dataset, name)
        platt = project_feature_set(roles["PLATT"].dataset, name)
        threshold = project_feature_set(roles["THRESHOLD"].dataset, name)
        result = _feature_threshold_result(
            name, fit, platt, threshold,
            roles["THRESHOLD"].expected_sessions, model_config,
            models_root / name)
        C.atomic_json(output / "feature_reports" / f"{name}.json", result)
        results.append(result)

    feasible = [row for row in results if row.policy_grid.status == "SELECTED"]
    best = (None if not feasible else min(feasible, key=lambda row: (
        -float(row.policy_grid.selected_evaluation.total_pnl_usd),
        float(row.policy_grid.selected_evaluation.max_drawdown_usd),
        row.feature_count, row.feature_set)))

    null_result = None
    if run_shuffled_control:
        control_name = (best.feature_set if best is not None else
                        max(results, key=lambda row: (
                            row.threshold_diagnostic.goal_auc
                            + row.threshold_diagnostic.wall_auc,
                            -row.feature_count)).feature_set)
        fit = project_feature_set(roles["FIT"].dataset, control_name)
        platt = project_feature_set(roles["PLATT"].dataset, control_name)
        threshold = project_feature_set(roles["THRESHOLD"].dataset, control_name)
        selector = _load_or_fit_selector(
            fit, models_root / f"{control_name}__SHUFFLED.selector.json")
        fit = selector.transform(fit)
        platt = selector.transform(platt)
        threshold = selector.transform(threshold)
        shuffled_fit = shuffle_confirmation_targets(fit, shuffled_seed)
        shuffled_platt = shuffle_confirmation_targets(platt, shuffled_seed + 1)
        try:
            null_model = _load_or_fit_model(
                shuffled_fit, shuffled_platt, model_config,
                models_root / f"{control_name}__SHUFFLED")
            prediction = null_model.predict(threshold)
            diagnostic = predictive_diagnostic(threshold, prediction)
            grid = score_confirmation_policies(
                threshold, prediction,
                expected_sessions=roles["THRESHOLD"].expected_sessions)
            null_core = {
                "schema": "QRE2CONFNULL1", "status": "MEASURED",
                "feature_set": control_name, "seed": shuffled_seed,
                "diagnostic": diagnostic.receipt_sha256,
                "policy_grid": grid.receipt_sha256,
            }
            null_result = ShuffledControlResult(
                "MEASURED", control_name, shuffled_seed, diagnostic, grid,
                None, C.object_sha256(null_core))
        except ConfirmationRefusal as exc:
            null_core = {
                "schema": "QRE2CONFNULL1",
                "status": "REFUSED_BY_LEARNER_CONTRACT",
                "feature_set": control_name, "seed": shuffled_seed,
                "refusal_reason": str(exc),
            }
            null_result = ShuffledControlResult(
                "REFUSED_BY_LEARNER_CONTRACT", control_name, shuffled_seed,
                None, None, str(exc), C.object_sha256(null_core))
        C.atomic_json(output / "shuffled_control.json", null_result)

    status = "SELECTED" if best is not None else "NO_FEASIBLE_THRESHOLD"
    core = {
        "schema": THRESHOLD_RUN_SCHEMA, "status": status,
        "stage": str(stage).upper(), "role_receipts": role_receipts,
        "features": tuple(row.receipt_sha256 for row in results),
        "selected_feature_set": None if best is None else best.feature_set,
        "selected_model_path": None if best is None else best.model_path,
        "selected_policy": (None if best is None else
                            best.policy_grid.selected.receipt_sha256),
        "shuffled_control": (None if null_result is None else
                             null_result.receipt_sha256),
        "forward_opened": False,
    }
    result = ThresholdExperimentResult(
        status, str(stage).upper(), dict(role_receipts),
        tuple(results), None if best is None else best.feature_set,
        None if best is None else best.model_path,
        None if best is None else best.policy_grid.selected.receipt_sha256,
        null_result, C.object_sha256(core))
    C.atomic_json(output / "threshold_result.json", result)
    return result


__all__ = [
    "AuthoritativeConfirmationSessionSpec", "CachedConfirmationSession",
    "ConfirmationRoleCorpus", "FeatureThresholdResult",
    "ShuffledControlResult", "ThresholdExperimentResult",
    "PredictiveDiagnostic", "cache_confirmation_feature_session",
    "cache_confirmation_opportunity_session", "canonical_stage_specs",
    "combine_feature_role", "confirmation_lane_registry",
    "discover_authoritative_session_specs", "load_opportunity_shards",
    "materialize_feature_cache", "materialize_opportunity_cache",
    "predictive_diagnostic", "project_feature_set",
    "run_threshold_experiment",
]
