#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile
from typing import Iterator


ARCHIVE_ROOT_ENV = "CODEX_TRANSCRIPT_ARCHIVE_ROOT"
ARCHIVE_DIRECTORY_MODE = 0o700
ARCHIVE_OBJECT_MODE = 0o600
COPY_CHUNK_BYTES = 1024 * 1024


class TranscriptArchiveError(Exception):
    pass


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
