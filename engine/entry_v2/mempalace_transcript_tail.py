"""Incremental transcript tail capture. Local durability before any hub call."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from .pod_local_lock import pod_local_lock_path
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    from .mempalace_continuity_spool import (
        DEFAULT_HOOK_STATE_DIR,
        _safe_id,
        validate_transcript_path,
    )
except ImportError:
    from mempalace_continuity_spool import (  # type: ignore
        DEFAULT_HOOK_STATE_DIR,
        _safe_id,
        validate_transcript_path,
    )


TAIL_SCHEMA = 1
DEFAULT_MAX_TAIL_BYTES = 8_000_000


def default_tail_dir() -> Path:
    override = os.environ.get("MEMPALACE_CONTINUITY_TAIL_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_HOOK_STATE_DIR / "tails"


def _cursor_path(tail_dir: Path, session_id: str) -> Path:
    return tail_dir / f"{_safe_id(session_id)}.cursor.json"


def _read_cursor(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file() or path.is_symlink():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("schema_version") != TAIL_SCHEMA:
        return None
    return value


def _atomic_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def capture_transcript_tail(
    payload: Mapping[str, Any],
    *,
    tail_dir: Path | None = None,
    max_bytes: int = DEFAULT_MAX_TAIL_BYTES,
) -> dict[str, Any]:
    """Copy unread transcript bytes.  Reset the cursor if the file shrank."""

    session_id = str(payload.get("session_id") or "")
    raw_path = payload.get("transcript_path")
    if not isinstance(raw_path, str) or not raw_path:
        return {"status": "no-transcript", "session_id": session_id}

    try:
        transcript = validate_transcript_path(raw_path)
    except (OSError, ValueError) as exc:
        return {
            "status": "invalid-transcript",
            "session_id": session_id,
            "error_type": type(exc).__name__,
        }

    directory = (tail_dir or default_tail_dir()).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    cursor_path = _cursor_path(directory, session_id)
    # Lock file on the pod-local overlay, keyed by the target (stale-network-flock,
    # 2026-08-22: a lock beside the target on /workspace outlives a dead pod).
    lock_path = pod_local_lock_path(cursor_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        info = transcript.stat()
        if not stat.S_ISREG(info.st_mode):
            return {"status": "invalid-transcript", "session_id": session_id}
        size = info.st_size
        cursor = _read_cursor(cursor_path)
        offset = 0
        reset = False
        if (
            cursor
            and cursor.get("transcript_path") == str(transcript)
            and isinstance(cursor.get("byte_offset"), int)
        ):
            offset = int(cursor["byte_offset"])
            if offset > size:
                offset = 0
                reset = True
            else:
                prefix_sha = cursor.get("prefix_sha256")
                if isinstance(prefix_sha, str) and offset > 0:
                    with transcript.open("rb") as handle:
                        actual = hashlib.sha256(handle.read(offset)).hexdigest()
                    if actual != prefix_sha:
                        offset = 0
                        reset = True
        elif cursor:
            reset = True

        if offset == size and not reset:
            return {
                "status": "tail_unchanged",
                "session_id": session_id,
                "byte_offset": offset,
                "transcript_path": str(transcript),
            }

        remaining = size - offset
        if remaining > max_bytes:
            remaining = max_bytes
        with transcript.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read(remaining)
            handle.seek(0)
            new_prefix = handle.read(offset + len(chunk))
        prefix_sha256 = hashlib.sha256(new_prefix).hexdigest()
        tail_name = f"{_safe_id(session_id)}.{offset}-{offset + len(chunk)}.jsonl"
        tail_path = directory / tail_name
        _atomic_write(tail_path, chunk)
        new_offset = offset + len(chunk)
        _atomic_write(
            cursor_path,
            (
                json.dumps(
                    {
                        "schema_version": TAIL_SCHEMA,
                        "session_id": session_id,
                        "transcript_path": str(transcript),
                        "byte_offset": new_offset,
                        "prefix_sha256": prefix_sha256,
                        "last_tail_path": str(tail_path),
                        "last_tail_sha256": hashlib.sha256(chunk).hexdigest(),
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8"),
        )
        return {
            "status": "tail_reset" if reset else "tail_appended",
            "session_id": session_id,
            "transcript_path": str(transcript),
            "tail_path": str(tail_path),
            "bytes_copied": len(chunk),
            "byte_offset": new_offset,
        }
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
