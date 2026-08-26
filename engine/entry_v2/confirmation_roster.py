"""Authoritative session discovery for confirmation experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from . import common as C
from .confirmation import ConfirmationRefusal
from .context_sources import CausalContextRepository, load_context_repository
from .contracts import SessionRef
from .diagnostic_inputs import fit_only_rehearsal_windows


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
            raise ConfirmationRefusal(
                "authoritative previous-session source is invalid")

    @property
    def session(self) -> SessionRef:
        return SessionRef(
            self.asset, self.trading_day,
            f"{self.asset}-{self.trading_day}")


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


def _manifest_rows(
    path: Path, schema: str,
) -> tuple[Mapping[str, str], ...]:
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeError) as exc:
        raise ConfirmationRefusal(
            f"cannot read authority manifest: {path}") from exc
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


def _previous_sessions(
    candidates: Mapping[int, Mapping[str, str]],
) -> dict[int, int | None]:
    previous_by_day: dict[int, int | None] = {}
    last_present: int | None = None
    for roster_day in sorted(candidates):
        previous_by_day[roster_day] = last_present
        candidate = candidates[roster_day]
        if (candidate["event_pack_sha256"] != "ABSENT"
                and candidate["status"] in {"READY", "NO_ATR14"}
                and int(candidate["raw_events"]) > 1
                and int(candidate["two_sided_events"]) > 1
                and int(candidate["sane_events"]) > 1):
            last_present = roster_day
    return previous_by_day


def _validate_authority_rows(
    asset: str, day: int, candidate: Mapping[str, str],
    teacher: Mapping[str, str],
) -> None:
    if (candidate["asset"] != asset or teacher["asset"] != asset
            or int(teacher["d8"]) != day
            or candidate["candidate_sha256"] != teacher["candidate_sha256"]
            or int(candidate["rows"]) != int(teacher["rows"])
            or int(teacher["ready"]) + int(teacher["refused"])
               != int(teacher["rows"])):
        raise ConfirmationRefusal("candidate/teacher authority rows differ")
    event_hash = candidate["event_pack_sha256"]
    if ((event_hash == "ABSENT")
            != (candidate["status"] in {"NO_LOCK", "NO_EVENTS"})
            or (event_hash == "ABSENT" and int(candidate["rows"]) != 0)):
        raise ConfirmationRefusal("candidate event/status authority differs")


def _session_spec(
    root: Path, asset: str, day: int,
    candidate: Mapping[str, str], teacher: Mapping[str, str],
    previous_day: int | None, candidates: Mapping[int, Mapping[str, str]],
    forecast_artifact_sha: str, forecast_receipt_sha: str,
) -> AuthoritativeConfirmationSessionSpec:
    event_hash = candidate["event_pack_sha256"]
    candidate_path = (root / candidate["candidate_file"]).resolve()
    teacher_path = (root / teacher["teacher_file"]).resolve()
    event_path = (None if event_hash == "ABSENT" else
                  str((root / f"events/{asset}/{day}.qre2").resolve()))
    previous_hash = ("ABSENT" if previous_day is None else
                     candidates[previous_day]["event_pack_sha256"])
    previous_path = (None if previous_day is None else
                     str((root / f"events/{asset}/{previous_day}.qre2").resolve()))
    spec = AuthoritativeConfirmationSessionSpec(
        asset, day, event_path, str(candidate_path), str(teacher_path),
        candidate["status"], event_hash, candidate["candidate_sha256"],
        teacher["teacher_sha256"], str(root), forecast_artifact_sha,
        forecast_receipt_sha, previous_path, previous_day, previous_hash)
    if (C.file_sha256(candidate_path) != spec.expected_candidate_sha256
            or C.file_sha256(teacher_path) != spec.expected_teacher_sha256
            or (event_path is not None and not Path(event_path).is_file())):
        raise ConfirmationRefusal("authority manifest payload pin differs")
    return spec


def discover_authoritative_session_specs(
    source_root: str | Path, window: tuple[int, int],
) -> tuple[AuthoritativeConfirmationSessionSpec, ...]:
    """Resolve exact event/candidate/teacher set algebra for one role."""

    root = Path(source_root).resolve()
    lower, upper = map(int, window)
    if lower > upper or upper >= C.HOLDOUT_START_D8:
        raise ConfirmationRefusal(
            "confirmation discovery window is invalid/sealed")
    output = []
    for asset in C.ASSETS:
        forecast_artifact = root / "forecast" / f"{asset}.qrf4.tsv"
        forecast_receipt = root / "forecast" / f"{asset}.qrf4.json"
        if not forecast_artifact.is_file() or not forecast_receipt.is_file():
            raise ConfirmationRefusal(
                "authoritative forward-vol artifact is absent")
        candidate_rows = _manifest_rows(
            root / "g1/candidates" / asset / "manifest.tsv",
            "QRE2G1CANDMAN2")
        teacher_rows = _manifest_rows(
            root / "g1/teacher" / asset / "manifest.tsv",
            "QRE2G1TEACHMAN2")
        candidates = {int(row["d8"]): row for row in candidate_rows}
        teachers = {int(row["d8"]): row for row in teacher_rows}
        if (len(candidates) != len(candidate_rows)
                or len(teachers) != len(teacher_rows)
                or set(candidates) != set(teachers)):
            raise ConfirmationRefusal(
                "candidate/teacher manifest rosters differ")
        previous_by_day = _previous_sessions(candidates)
        forecast_artifact_sha = C.file_sha256(forecast_artifact)
        forecast_receipt_sha = C.file_sha256(forecast_receipt)
        for day in sorted(candidates):
            if (not lower <= day <= upper
                    or C.denominator_disposition(asset, day) != "INCLUDE"):
                continue
            candidate = candidates[day]
            teacher = teachers[day]
            _validate_authority_rows(asset, day, candidate, teacher)
            output.append(_session_spec(
                root, asset, day, candidate, teacher, previous_by_day[day],
                candidates, forecast_artifact_sha, forecast_receipt_sha))
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
        raise ConfirmationRefusal(
            "confirmation role request is empty/duplicated")
    unknown = set(requested) - set(windows)
    if unknown:
        raise ConfirmationRefusal(
            f"unknown confirmation roles: {sorted(unknown)}")
    return MappingProxyType({
        role: discover_authoritative_session_specs(source_root, windows[role])
        for role in requested})


_CONTEXT_REPOSITORY_CACHE: dict[str, CausalContextRepository] = {}


def _context_repository(
    spec: AuthoritativeConfirmationSessionSpec,
) -> CausalContextRepository:
    repository = _CONTEXT_REPOSITORY_CACHE.get(spec.asset)
    if repository is None:
        repository = load_context_repository(
            spec.asset, C.DEVELOPMENT_END_D8)
        _CONTEXT_REPOSITORY_CACHE[spec.asset] = repository
    return repository


def _source_identity(
    spec: AuthoritativeConfirmationSessionSpec,
) -> dict[str, object]:
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
        raise ConfirmationRefusal(
            "authoritative context receipt is invalid")
    if (event_sha != spec.expected_event_sha256
            or candidate_sha != spec.expected_candidate_sha256
            or teacher_sha != spec.expected_teacher_sha256
            or forecast_artifact_sha
               != spec.expected_forecast_artifact_sha256
            or forecast_receipt_sha
               != spec.expected_forecast_receipt_sha256
            or previous_sha != spec.expected_previous_event_sha256):
        raise ConfirmationRefusal(
            "confirmation source changed after discovery")
    return {
        "asset": spec.asset,
        "trading_day": spec.trading_day,
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


__all__ = [
    "AuthoritativeConfirmationSessionSpec",
    "canonical_stage_specs",
    "discover_authoritative_session_specs",
]
