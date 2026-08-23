#!/usr/bin/env python3
"""Adapt the installed OptMem CLI to Codex lifecycle hook JSON."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Iterator, Sequence, TextIO


MEMO_CANDIDATES = (
    Path("/home/algo/.optmem/memo"),
    Path("/workspace/.optmem/memo"),
)
PYTHON_FALLBACK = Path("/usr/bin/python3")
HOOK_DEADLINE_SECONDS = 24.0
HEALTH_DEADLINE_SECONDS = 4.0
MAX_WAKE_CALLS = 32
NEXT_WAKE_RE = re.compile(
    r"^Not awake yet\. Run: .+? wake ([1-9][0-9]*) ([1-9][0-9]*)\s*$",
    re.MULTILINE,
)
PENDING_NAP_RE = re.compile(
    r'\ACompress memories #[0-9]+-[0-9]+ into one line of at most [0-9]+ bytes\.\n'
    r'Keep what has lasting effect, drop what does not\. Invent nothing\.\n\n'
    r'.+\nRun: .+? nap [0-9]+-[0-9]+ "<your line>"\n?\Z',
    re.DOTALL,
)
ARCHIVE_ROOT_ENV = "CODEX_TRANSCRIPT_ARCHIVE_ROOT"
ARCHIVE_DIRECTORY_MODE = 0o700
ARCHIVE_OBJECT_MODE = 0o600
COPY_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class MemoResult:
    returncode: int
    output: str


class TranscriptArchiveError(Exception):
    """Report a transcript that could not be archived without data loss."""


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


def find_memo_executable() -> Path | None:
    """Return the first installed OptMem CLI without inspecting its memory."""
    return next((path for path in MEMO_CANDIDATES if path.is_file()), None)


def shebang_python_is_missing(result: MemoResult) -> bool:
    return (
        result.returncode == 127
        and "python3" in result.output
        and "No such file or directory" in result.output
    )


def timeout_result(error: subprocess.TimeoutExpired) -> MemoResult:
    """Return whatever a timed-out command managed to print, plus why it stopped."""
    partial = error.stdout or ""
    if isinstance(partial, bytes):
        partial = partial.decode("utf-8", errors="replace")
    return MemoResult(124, partial + "OptMem lifecycle command timed out.\n")


def run_process(command: Sequence[str], deadline: float) -> MemoResult:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return MemoResult(124, "OptMem lifecycle deadline expired.\n")
    try:
        completed = subprocess.run(
            command, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=remaining)
    except subprocess.TimeoutExpired as error:
        return timeout_result(error)
    return MemoResult(completed.returncode, completed.stdout)


def run_memo(memo: Path, arguments: Sequence[str], deadline: float) -> MemoResult:
    """Run OptMem directly, using Python only for a missing shebang interpreter."""
    try:
        direct = run_process((str(memo), *arguments), deadline)
    except FileNotFoundError:
        if not memo.is_file():
            raise
        return run_process((str(PYTHON_FALLBACK), str(memo), *arguments), deadline)
    if shebang_python_is_missing(direct):
        return run_process((str(PYTHON_FALLBACK), str(memo), *arguments), deadline)
    return direct


def next_wake_arguments(output: str) -> tuple[str, ...] | None:
    """Return the next wake page OptMem asked for, or None when it is done."""
    matches = list(NEXT_WAKE_RE.finditer(output))
    if not matches:
        return None
    page, snapshot = matches[-1].groups()
    return ("wake", page, snapshot)


def collect_wake_pages(memo: Path, deadline: float, outputs: list[str]) -> str | None:
    """Follow every wake page, returning an error line when one is reached."""
    arguments: tuple[str, ...] = ("wake",)
    seen: set[tuple[str, ...]] = set()
    for _ in range(MAX_WAKE_CALLS):
        if arguments in seen:
            return f"OptMem lifecycle error: repeated wake arguments {arguments!r}.\n"
        seen.add(arguments)
        result = run_memo(memo, arguments, deadline)
        outputs.append(result.output)
        following = next_wake_arguments(result.output) if result.returncode == 0 else None
        if following is None:
            return None
        arguments = following
    return f"OptMem lifecycle error: wake exceeded {MAX_WAKE_CALLS} calls.\n"


def session_start_context() -> str:
    memo = find_memo_executable()
    if memo is None:
        expected = ", ".join(str(path) for path in MEMO_CANDIDATES)
        return f"OptMem lifecycle error: no memo executable found; expected one of {expected}.\n"
    outputs: list[str] = []
    error = collect_wake_pages(memo, time.monotonic() + HOOK_DEADLINE_SECONDS, outputs)
    if error is not None:
        outputs.append(error)
    return "".join(outputs)


def advisory_precompact_response(reason: str) -> dict[str, object]:
    """Report a PreCompact problem without ever refusing the compaction.

    WHY (D-108, and the 2026-08-23 deadlock): this hook used to return
    `continue: False` while an OptMem compression was pending. Compaction is
    requested exactly when the context is full, so refusing it left the session
    with no way forward and no way to settle the compression. Continuity hooks
    report; only enforcement gates deny.
    """
    return {"systemMessage": reason}


def transcript_archive_failure(
    payload: dict[str, object], stderr: TextIO
) -> dict[str, object] | None:
    if "transcript_path" not in payload:
        return None
    try:
        archive_transcript(payload["transcript_path"])
    except (TranscriptArchiveError, OSError) as error:
        reason = f"Transcript archive failed: {error}\n"
        stderr.write(reason)
        return advisory_precompact_response(reason)
    return None


def nap_response(result: MemoResult, stderr: TextIO) -> dict[str, object]:
    """Turn one nap probe into an advisory response, never a refusal."""
    if result.returncode == 0 and PENDING_NAP_RE.fullmatch(result.output):
        return advisory_precompact_response(result.output)
    if result.returncode == 0 and result.output == "Nothing left to compress.\n":
        return {}
    stderr.write("OptMem precompact check did not produce a recognized result "
                 f"(exit {result.returncode}); compaction continues.\n")
    return {}


def pre_compact_response(payload: dict[str, object], stderr: TextIO) -> dict[str, object]:
    archive_failure = transcript_archive_failure(payload, stderr)
    if archive_failure is not None:
        return archive_failure
    memo = find_memo_executable()
    if memo is None:
        stderr.write("OptMem precompact check skipped: memo executable not found.\n")
        return {}
    return nap_response(run_memo(memo, ("nap",),
                                 time.monotonic() + HOOK_DEADLINE_SECONDS), stderr)


def post_compact_health_check(stderr: TextIO) -> None:
    memo = find_memo_executable()
    if memo is None:
        stderr.write("OptMem postcompact health check skipped: memo executable not found.\n")
        return
    result = run_memo(
        memo,
        ("config",),
        time.monotonic() + HEALTH_DEADLINE_SECONDS,
    )
    if result.returncode != 0:
        stderr.write(
            "OptMem postcompact health check failed "
            f"(exit {result.returncode}); SessionStart source=compact still owns recall.\n"
        )


def write_hook_json(value: object, stdout: TextIO) -> None:
    json.dump(value, stdout, ensure_ascii=False)
    stdout.write("\n")


EXPECTED_EVENTS = {"session-start": "SessionStart", "pre-compact": "PreCompact",
                   "post-compact": "PostCompact"}


def require_event(command: str, payload: dict[str, object]) -> None:
    """Refuse a payload whose event does not match the command that ran."""
    expected = EXPECTED_EVENTS[command]
    actual = payload.get("hook_event_name")
    if actual != expected:
        raise ValueError(f"{command} expected hook_event_name={expected!r}, got {actual!r}")


def session_start_response() -> dict[str, object]:
    """Return the wake output as SessionStart context."""
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": session_start_context()}}


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run one Codex lifecycle event."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    payload = json.load(stdin)
    if len(arguments) != 1 or arguments[0] not in EXPECTED_EVENTS:
        raise ValueError(f"unknown lifecycle command {arguments!r}")
    command = arguments[0]
    require_event(command, payload)
    if command == "session-start":
        write_hook_json(session_start_response(), stdout)
    elif command == "pre-compact":
        write_hook_json(pre_compact_response(payload, stderr), stdout)
    else:
        post_compact_health_check(stderr)
        write_hook_json({}, stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
