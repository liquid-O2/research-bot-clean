#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile
from typing import Iterator


ARCHIVE_ROOT_ENV = "CODEX_TRANSCRIPT_ARCHIVE_ROOT"
ARCHIVE_DIRECTORY_MODE = 0o700
ARCHIVE_OBJECT_MODE = 0o600
COPY_CHUNK_BYTES = 1024 * 1024
PENDING_SCHEMA_VERSION = 1
PENDING_RECONCILE_LIMIT = 8


class TranscriptArchiveError(Exception):
    pass


@dataclass(frozen=True)
class PendingTranscript:
    source_path: Path
    device: int
    inode: int
    observed_bytes: int
    prefix_sha256: str
    turn_id: str
    generation: str


def transcript_archive_root() -> Path:
    override = os.environ.get(ARCHIVE_ROOT_ENV)
    if override:
        return Path(override)
    return Path.home() / ".local" / "state" / "codex" / "transcript-archive"


def ensure_private_directory(directory: Path) -> None:
    directory.mkdir(mode=ARCHIVE_DIRECTORY_MODE, parents=True, exist_ok=True)
    metadata = directory.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise TranscriptArchiveError(f"archive directory is not a directory: {directory}")
    directory.chmod(ARCHIVE_DIRECTORY_MODE)


def fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def source_version(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def open_regular_file(path: Path, label: str) -> tuple[int, tuple[int, ...]]:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise TranscriptArchiveError(f"{label} is not a regular file: {path}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened_metadata = os.fstat(descriptor)
        if source_version(metadata) != source_version(opened_metadata):
            raise TranscriptArchiveError(f"{label} changed while opening: {path}")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor, source_version(opened_metadata)


def stream_chunks(descriptor: int) -> Iterator[bytes]:
    """Yield the source file in chunks without closing the caller's descriptor."""
    with os.fdopen(descriptor, "rb", closefd=False) as source:
        while chunk := source.read(COPY_CHUNK_BYTES):
            yield chunk


def copy_transcript(descriptor: int, destination: Path) -> str:
    digest = sha256()
    with destination.open("wb") as output:
        for chunk in stream_chunks(descriptor):
            output.write(chunk)
            digest.update(chunk)
        output.flush()
        os.fsync(output.fileno())
    destination.chmod(ARCHIVE_OBJECT_MODE)
    return digest.hexdigest()


def digest_archive_object(destination: Path) -> str:
    descriptor, initial_version = open_regular_file(destination, "archive object")
    if stat.S_IMODE(os.fstat(descriptor).st_mode) != ARCHIVE_OBJECT_MODE:
        os.close(descriptor)
        raise TranscriptArchiveError(f"archive object has an unsafe mode: {destination}")
    digest = sha256()
    try:
        for chunk in stream_chunks(descriptor):
            digest.update(chunk)
        if not file_matches_version(destination, descriptor, initial_version):
            raise TranscriptArchiveError(f"archive object changed while reading: {destination}")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def publish_transcript(temporary: Path, destination: Path, expected_digest: str) -> None:
    try:
        os.link(temporary, destination)
    except FileExistsError:
        actual_digest = digest_archive_object(destination)
        if actual_digest != expected_digest:
            raise TranscriptArchiveError(
                f"archive object digest {actual_digest} did not match {expected_digest}: {destination}"
            )
    finally:
        temporary.unlink(missing_ok=True)
    fsync_directory(destination.parent)


def file_matches_version(source: Path, descriptor: int, expected: tuple[int, ...]) -> bool:
    try:
        return (
            source_version(os.fstat(descriptor)) == expected
            and source_version(source.lstat()) == expected
        )
    except OSError:
        return False


def create_archive_temporary() -> tuple[int, Path]:
    root = transcript_archive_root()
    ensure_private_directory(root)
    objects = root / "objects"
    ensure_private_directory(objects)
    temporary_descriptor, raw_temporary = tempfile.mkstemp(prefix=".archive-", dir=objects)
    return temporary_descriptor, Path(raw_temporary)


def copy_and_publish_transcript(
    source: Path, descriptor: int, initial_version: tuple[int, ...]
) -> Path:
    temporary_descriptor, temporary = create_archive_temporary()
    os.close(temporary_descriptor)
    try:
        digest = copy_transcript(descriptor, temporary)
        if not file_matches_version(source, descriptor, initial_version):
            raise TranscriptArchiveError(f"transcript source changed while copying: {source}")
        shard = temporary.parent / digest[:2]
        ensure_private_directory(shard)
        destination = shard / f"{digest}.jsonl"
        publish_transcript(temporary, destination, digest)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def archive_transcript(raw_source: object) -> Path:
    if not isinstance(raw_source, str) or not raw_source:
        raise TranscriptArchiveError(
            f"transcript_path must be a non-empty string, got {raw_source!r}")
    source = Path(raw_source)
    try:
        descriptor, initial_version = open_regular_file(source, "transcript source")
    except OSError as error:
        raise TranscriptArchiveError(f"cannot open transcript source {source}: {error}") from error
    try:
        return copy_and_publish_transcript(source, descriptor, initial_version)
    finally:
        os.close(descriptor)


def validate_turn_id(raw_turn_id: object) -> str:
    if not isinstance(raw_turn_id, str) or not raw_turn_id:
        raise TranscriptArchiveError(
            f"turn_id must be a non-empty string, got {raw_turn_id!r}"
        )
    return raw_turn_id


def canonical_open_source(raw_source: object) -> tuple[Path, int, tuple[int, ...]]:
    if not isinstance(raw_source, str) or not raw_source:
        raise TranscriptArchiveError(
            f"transcript_path must be a non-empty string, got {raw_source!r}"
        )
    source = Path(raw_source).absolute()
    try:
        descriptor, version = open_regular_file(source, "transcript source")
    except OSError as error:
        raise TranscriptArchiveError(f"cannot open transcript source {source}: {error}") from error
    try:
        canonical = Path(os.path.realpath(source))
        if source_version(canonical.lstat()) != version:
            raise TranscriptArchiveError(f"transcript source changed while resolving: {source}")
        return canonical, descriptor, version
    except Exception:
        os.close(descriptor)
        raise


def digest_prefix(descriptor: int, byte_count: int) -> str:
    digest = sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    remaining = byte_count
    while remaining:
        chunk = os.read(descriptor, min(COPY_CHUNK_BYTES, remaining))
        if not chunk:
            raise TranscriptArchiveError(
                f"transcript ended at {byte_count - remaining} bytes, expected {byte_count}"
            )
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


def pending_paths(source: Path) -> tuple[Path, Path]:
    pending = transcript_archive_root() / "pending"
    ensure_private_directory(pending)
    name = sha256(os.fsencode(source)).hexdigest()
    return pending / f"{name}.json", pending / f".{name}.lock"


@contextmanager
def marker_lock(lock_path: Path) -> Iterator[None]:
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, ARCHIVE_OBJECT_MODE)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise TranscriptArchiveError(f"pending marker lock is not a regular file: {lock_path}")
        os.fchmod(descriptor, ARCHIVE_OBJECT_MODE)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def write_pending_marker(marker_path: Path, marker: dict[str, object]) -> None:
    descriptor, raw_temporary = tempfile.mkstemp(prefix=".pending-", dir=marker_path.parent)
    temporary = Path(raw_temporary)
    try:
        os.fchmod(descriptor, ARCHIVE_OBJECT_MODE)
        encoded = (json.dumps(marker, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, marker_path)
        marker_path.chmod(ARCHIVE_OBJECT_MODE)
        fsync_directory(marker_path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def pending_marker_fields(
    source: Path, version: tuple[int, ...], prefix_digest: str, turn_id: str
) -> dict[str, object]:
    return {
        "schema_version": PENDING_SCHEMA_VERSION,
        "source_path": str(source),
        "device": version[0],
        "inode": version[1],
        "observed_bytes": version[3],
        "prefix_sha256": prefix_digest,
        "turn_id": turn_id,
        "generation": secrets.token_hex(16),
    }


def defer_transcript(raw_source: object, raw_turn_id: object) -> Path:
    turn_id = validate_turn_id(raw_turn_id)
    source, descriptor, version = canonical_open_source(raw_source)
    try:
        prefix_digest = digest_prefix(descriptor, version[3])
        if not file_matches_version(source, descriptor, version):
            raise TranscriptArchiveError(f"transcript source changed while deferring: {source}")
    finally:
        os.close(descriptor)
    marker_path, lock_path = pending_paths(source)
    marker = pending_marker_fields(source, version, prefix_digest, turn_id)
    with marker_lock(lock_path):
        write_pending_marker(marker_path, marker)
    return marker_path


def require_int_field(raw: object, field: str, marker_path: Path) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
        raise TranscriptArchiveError(
            f"pending marker field {field!r} must be a non-negative integer: {marker_path}"
        )
    return raw


def require_string_field(raw: object, field: str, marker_path: Path) -> str:
    if not isinstance(raw, str) or not raw:
        raise TranscriptArchiveError(
            f"pending marker field {field!r} must be a non-empty string: {marker_path}"
        )
    return raw


def read_pending_fields(marker_path: Path) -> dict[str, object]:
    descriptor, version = open_regular_file(marker_path, "pending marker")
    try:
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != ARCHIVE_OBJECT_MODE:
            raise TranscriptArchiveError(f"pending marker has an unsafe mode: {marker_path}")
        with os.fdopen(descriptor, "rb", closefd=False) as marker_file:
            raw = json.load(marker_file)
        if not file_matches_version(marker_path, descriptor, version):
            raise TranscriptArchiveError(f"pending marker changed while reading: {marker_path}")
    finally:
        os.close(descriptor)
    if not isinstance(raw, dict) or raw.get("schema_version") != PENDING_SCHEMA_VERSION:
        raise TranscriptArchiveError(f"pending marker has an unsupported schema: {marker_path}")
    return raw


def parse_prefix_digest(raw: object, marker_path: Path) -> str:
    digest = require_string_field(raw, "prefix_sha256", marker_path)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise TranscriptArchiveError(f"pending marker prefix_sha256 is invalid: {marker_path}")
    return digest


def parse_pending_marker(marker_path: Path) -> PendingTranscript:
    raw = read_pending_fields(marker_path)
    source = Path(require_string_field(raw.get("source_path"), "source_path", marker_path))
    if not source.is_absolute():
        raise TranscriptArchiveError(f"pending marker source_path must be absolute: {marker_path}")
    return PendingTranscript(
        source, require_int_field(raw.get("device"), "device", marker_path),
        require_int_field(raw.get("inode"), "inode", marker_path),
        require_int_field(raw.get("observed_bytes"), "observed_bytes", marker_path),
        parse_prefix_digest(raw.get("prefix_sha256"), marker_path),
        require_string_field(raw.get("turn_id"), "turn_id", marker_path),
        require_string_field(raw.get("generation"), "generation", marker_path),
    )


def decode_appended_record(line: bytes, marker: PendingTranscript) -> object:
    try:
        return json.loads(line)
    except json.JSONDecodeError as error:
        raise TranscriptArchiveError(
            f"transcript has malformed JSON after {marker.observed_bytes} bytes: {marker.source_path}"
        ) from error


def has_matching_terminal(descriptor: int, marker: PendingTranscript) -> bool:
    os.lseek(descriptor, marker.observed_bytes, os.SEEK_SET)
    with os.fdopen(descriptor, "rb", closefd=False) as source:
        appended = source.read()
    if not appended or not appended.endswith(b"\n"):
        return False
    last_record: object = None
    for line in filter(None, appended.splitlines()):
        last_record = decode_appended_record(line, marker)
    if not isinstance(last_record, dict) or last_record.get("type") != "event_msg":
        return False
    payload = last_record.get("payload")
    return isinstance(payload, dict) and payload.get("type") == "task_complete" and payload.get("turn_id") == marker.turn_id


def pending_source_metadata(marker: PendingTranscript) -> os.stat_result | None:
    try:
        metadata = marker.source_path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise TranscriptArchiveError(
            f"pending transcript source is not a regular file: {marker.source_path}"
        )
    return metadata


def open_pending_descriptor(marker: PendingTranscript) -> int | None:
    try:
        return os.open(
            marker.source_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        raise TranscriptArchiveError(
            f"cannot open pending transcript source {marker.source_path}: {error}"
        ) from error


def open_pending_source(marker: PendingTranscript) -> tuple[int, tuple[int, ...]] | None:
    metadata = pending_source_metadata(marker)
    if metadata is None:
        return None
    descriptor = open_pending_descriptor(marker)
    if descriptor is None:
        return None
    opened = os.fstat(descriptor)
    if opened.st_dev != marker.device or opened.st_ino != marker.inode:
        os.close(descriptor)
        raise TranscriptArchiveError(f"pending transcript source was replaced: {marker.source_path}")
    if metadata.st_dev != opened.st_dev or metadata.st_ino != opened.st_ino:
        os.close(descriptor)
        raise TranscriptArchiveError(f"pending transcript source changed while opening: {marker.source_path}")
    version = source_version(opened)
    if source_version(metadata) != version:
        os.close(descriptor)
        return None
    return descriptor, version


def archive_ready_pending(marker: PendingTranscript) -> Path | None:
    opened = open_pending_source(marker)
    if opened is None:
        return None
    descriptor, version = opened
    try:
        if version[3] < marker.observed_bytes:
            raise TranscriptArchiveError(f"pending transcript source shrank: {marker.source_path}")
        if digest_prefix(descriptor, marker.observed_bytes) != marker.prefix_sha256:
            raise TranscriptArchiveError(f"pending transcript prefix changed: {marker.source_path}")
        if not file_matches_version(marker.source_path, descriptor, version):
            return None
        if not has_matching_terminal(descriptor, marker):
            return None
        if not file_matches_version(marker.source_path, descriptor, version):
            return None
        os.lseek(descriptor, 0, os.SEEK_SET)
        return copy_and_publish_transcript(marker.source_path, descriptor, version)
    finally:
        os.close(descriptor)


def reconcile_pending_marker(marker_path: Path) -> None:
    lock_path = marker_path.with_name(f".{marker_path.stem}.lock")
    with marker_lock(lock_path):
        if not marker_path.exists():
            return
        marker = parse_pending_marker(marker_path)
        destination = archive_ready_pending(marker)
        if destination is None:
            return
        current = parse_pending_marker(marker_path)
        if current.generation != marker.generation:
            return
        fsync_directory(destination.parent)
        marker_path.unlink()
        fsync_directory(marker_path.parent)


def reconcile_pending_transcripts(limit: int = PENDING_RECONCILE_LIMIT) -> None:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise TranscriptArchiveError(f"reconciliation limit must be a positive integer, got {limit!r}")
    pending = transcript_archive_root() / "pending"
    ensure_private_directory(pending)
    failures: list[Exception] = []
    for marker_path in sorted(pending.glob("*.json"))[:limit]:
        try:
            reconcile_pending_marker(marker_path)
        except Exception as error:
            failures.append(error)
    if failures:
        raise TranscriptArchiveError(
            f"failed to reconcile {len(failures)} pending transcript marker(s): {failures[0]}"
        ) from failures[0]
