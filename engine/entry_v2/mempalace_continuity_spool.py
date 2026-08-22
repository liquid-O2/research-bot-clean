"""Atomic, bounded continuity spool for Codex/Grok/Claude compaction hooks.

The 6k checkpoint is a pointer plus last UI messages.  It is never the
memory.  Authoritative stores are the full transcript files (Codex JSONL,
Claude JSONL, Grok chat_history.jsonl, Grok compaction/segment_*.md) and
the HTTP palace drawers mined from those files.  Hook processes never
open a second ChromaDB writer.
"""

from __future__ import annotations

import collections
import fcntl
import hashlib
import json
import os
from .pod_local_lock import pod_local_lock_path
import re
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_MAX_CHECKPOINT_CHARS = 6_000
DEFAULT_MAX_SPOOL_BYTES = 48_000
DEFAULT_MAX_MESSAGE_CHARS = 3_000
DEFAULT_MAX_MESSAGES = 64
DEFAULT_RECONCILE_LIMIT = 2
WORKSPACE_MEMPALACE_ROOT = Path("/workspace/.mempalace")
DEFAULT_HOOK_STATE_DIR = WORKSPACE_MEMPALACE_ROOT / "hook_state"
DEFAULT_JOURNAL_PATH = Path("/workspace/journal.md")
DEFAULT_MAX_JOURNAL_BYTES = 64_000_000
JOURNAL_ENTRY_PREFIX = "<!-- CODEX_CONTINUITY_ENTRY sha256="
JOURNAL_ENTRY_SUFFIX = "<!-- /CODEX_CONTINUITY_ENTRY -->"


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]+")
_HEX_HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
_SENSITIVE_TAG_RE = re.compile(
    r"<(?:environment_context|permissions(?:\s+instructions)?|skills_instructions|"
    r"apps_instructions|plugins_instructions|recommended_plugins)\b[^>]*>.*?"
    r"</(?:environment_context|permissions(?:\s+instructions)?|skills_instructions|"
    r"apps_instructions|plugins_instructions|recommended_plugins)>",
    re.IGNORECASE | re.DOTALL,
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [^-\n]*(?:PRIVATE KEY|OPENSSH KEY)-----.*?"
    r"-----END [^-\n]*(?:PRIVATE KEY|OPENSSH KEY)-----",
    re.IGNORECASE | re.DOTALL,
)
_SECRET_ASSIGN_RE = re.compile(
    r"(?im)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
    r"password|passwd|secret|client[_-]?secret|private[_-]?key|credential|cookie)\b"
    r"\s*(?:=|:|\bis\b)\s*)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s,;\n]+)"
)
_AUTH_HEADER_RE = re.compile(r"(?im)(\bauthorization\s*:\s*(?:bearer|basic)\s+)\S+")
_URL_CREDENTIAL_RE = re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@")
_KNOWN_TOKEN_RES = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_id(value: Any) -> str:
    text = value if isinstance(value, str) else ""
    return _SAFE_ID_RE.sub("", text)[:96] or "unknown"


def default_spool_dir() -> Path:
    override = os.environ.get("MEMPALACE_CONTINUITY_SPOOL_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_HOOK_STATE_DIR / "continuity_spool"


def default_journal_path() -> Path:
    """Return the local append-only continuity journal destination."""

    override = os.environ.get("MEMPALACE_CONTINUITY_JOURNAL_PATH", "").strip()
    path = Path(override).expanduser() if override else DEFAULT_JOURNAL_PATH
    if not path.is_absolute():
        raise ValueError("continuity journal path must be absolute")
    return path


def append_receipt_log(kind: str, receipt: Mapping[str, Any]) -> None:
    """Append content-free hook evidence under the workspace state root."""

    try:
        DEFAULT_HOOK_STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(DEFAULT_HOOK_STATE_DIR, 0o700)
        path = DEFAULT_HOOK_STATE_DIR / "hook.log"
        encoded = (
            f"[{datetime.now().strftime('%H:%M:%S')}] CONTINUITY {kind} "
            + json.dumps(dict(receipt), sort_keys=True)
            + "\n"
        ).encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
    except OSError:
        pass


def _allowed_transcript_roots() -> tuple[Path, ...]:
    override = os.environ.get("MEMPALACE_CONTINUITY_ALLOWED_ROOTS", "").strip()
    if override:
        roots = [Path(part).expanduser().resolve() for part in override.split(os.pathsep) if part]
        return tuple(roots)
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", str(home / ".codex")))
    grok_home = Path(os.environ.get("GROK_HOME", str(home / ".grok")))
    claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude")))
    return (
        codex_home.expanduser().resolve(),
        (grok_home / "sessions").expanduser().resolve(),
        (claude_home / "projects").expanduser().resolve(),
        Path("/workspace/.mempalace/sources").resolve(),
    )


def validate_transcript_path(raw_path: Any) -> Path:
    """Resolve a regular transcript under an approved root.

    Grok compaction segments are markdown (``segment_*.md``, ``INDEX.md``).
    Live Grok/Claude/Codex transcripts are JSONL.
    """

    if not isinstance(raw_path, str) or not raw_path or ".." in Path(raw_path).parts:
        raise ValueError("missing or unsafe transcript path")
    path = Path(raw_path).expanduser().resolve()
    suffix = path.suffix.lower()
    if suffix not in {".jsonl", ".json", ".md"}:
        raise ValueError("unsupported transcript extension")
    if suffix == ".md" and path.name != "INDEX.md" and not path.name.startswith("segment_"):
        raise ValueError("unsupported markdown transcript name")
    if not any(path == root or path.is_relative_to(root) for root in _allowed_transcript_roots()):
        raise ValueError("transcript is outside approved roots")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("transcript is not a regular file")
    return path


def discover_transcript_path(payload: Mapping[str, Any]) -> str:
    """Find the live transcript when the hook payload omits transcriptPath.

    Grok PreCompact often has sessionId/cwd but no transcript path.  Codex
    usually passes the JSONL path explicitly.
    """

    existing = payload.get("transcript_path") or payload.get("transcriptPath")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    session_id = str(
        payload.get("session_id")
        or payload.get("sessionId")
        or os.environ.get("GROK_SESSION_ID")
        or ""
    ).strip()
    if not session_id:
        return ""
    grok_home = Path(os.environ.get("GROK_HOME", str(Path.home() / ".grok"))).expanduser()
    sessions = grok_home / "sessions"
    if sessions.is_dir():
        direct = sessions / session_id / "chat_history.jsonl"
        if direct.is_file():
            return str(direct.resolve())
        try:
            for child in sessions.rglob("chat_history.jsonl"):
                if child.parent.name == session_id and child.is_file():
                    return str(child.resolve())
        except OSError:
            pass
    claude_home = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    ).expanduser()
    projects = claude_home / "projects"
    if projects.is_dir():
        named = list(projects.rglob(f"{session_id}.jsonl"))
        if named:
            return str(named[0].resolve())
    return ""


def list_session_memory_files(transcript: Path) -> list[dict[str, Any]]:
    """Hash the live transcript and Grok compaction segments beside it."""

    files: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        key = str(resolved)
        if key in seen:
            return
        item = _hash_regular_file(resolved, max_bytes=50_000_000)
        if item is None:
            return
        seen.add(key)
        files.append(item)

    add(transcript)
    session_dir = transcript.parent
    compact_dir = session_dir / "compaction"
    add(compact_dir / "INDEX.md")
    if compact_dir.is_dir():
        try:
            for segment in sorted(compact_dir.glob("segment_*.md")):
                add(segment)
        except OSError:
            pass
    return files


def render_file_pointers(files: Sequence[Mapping[str, Any]]) -> str:
    if not files:
        return ""
    lines = [
        "Authoritative files (READ THESE. The checkpoint body is not the memory.):",
    ]
    for item in files:
        lines.append(
            f"- `{item.get('path')}` sha256={item.get('sha256')} bytes={item.get('bytes')}"
        )
    lines.append(
        "After compact, read compaction/INDEX.md then every segment_*.md "
        "with read_file/grep. Do not rely on the 6k checkpoint or the "
        "compaction summary."
    )
    return "\n".join(lines)


def redact_text(text: str) -> tuple[str, int]:
    """Remove common credential forms and injected environment blocks."""

    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    redactions = 0

    def replace(pattern: re.Pattern[str], value: str, source: str) -> str:
        nonlocal redactions
        updated, count = pattern.subn(value, source)
        redactions += count
        return updated

    text = replace(_SENSITIVE_TAG_RE, "[REDACTED INJECTED CONTEXT]", text)
    text = replace(_PRIVATE_KEY_RE, "[REDACTED PRIVATE KEY]", text)
    text = replace(_SECRET_ASSIGN_RE, r"\1[REDACTED]", text)
    text = replace(_AUTH_HEADER_RE, r"\1[REDACTED]", text)
    text = replace(_URL_CREDENTIAL_RE, r"\1[REDACTED]@", text)
    for pattern in _KNOWN_TOKEN_RES:
        text = replace(pattern, "[REDACTED TOKEN]", text)

    # Remove non-printing controls while preserving tabs/newlines used in code.
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    return text.strip(), redactions


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
        return ""
    chunks: list[str] = []
    for block in content:
        if not isinstance(block, Mapping):
            continue
        block_type = str(block.get("type", "")).lower()
        value = block.get("text")
        if block_type == "text" and isinstance(value, str):
            chunks.append(value)
    return "\n".join(chunks)


def _message_from_text(role: str, raw_text: str, phase: str = "") -> dict[str, str] | None:
    if not raw_text.strip():
        return None
    safe_text, redactions = redact_text(raw_text)
    if not safe_text:
        return None
    if len(safe_text) > DEFAULT_MAX_MESSAGE_CHARS:
        safe_text = safe_text[: DEFAULT_MAX_MESSAGE_CHARS - 34] + "\n[TRUNCATED MESSAGE IN SPOOL]"
    return {
        "role": role,
        "phase": phase,
        "text": safe_text,
        "redactions": str(redactions),
    }


def _completed_message(entry: Mapping[str, Any]) -> tuple[dict[str, str] | None, bool]:
    """Return a safe UI message and whether this is a compaction boundary."""

    entry_type = entry.get("type")
    if entry_type == "event_msg":
        payload = entry.get("payload")
        if not isinstance(payload, Mapping) or payload.get("type") != "item_completed":
            return None, False
        item = payload.get("item")
        if not isinstance(item, Mapping):
            return None, False
        item_type = item.get("type")
        if item_type == "ContextCompaction":
            return None, True
        if item_type not in {"UserMessage", "AgentMessage"}:
            return None, False
        role = "user" if item_type == "UserMessage" else "assistant"
        phase = item.get("phase") if isinstance(item.get("phase"), str) else ""
        return _message_from_text(role, _content_text(item.get("content")), phase), False

    # Grok compaction_meta lines are summaries injected after compact. Keep
    # them out of the spool; do not treat them as a Codex-style boundary that
    # wipes earlier messages from a still-growing JSONL.
    if entry.get("synthetic_reason"):
        return None, False
    if entry_type in {"user", "assistant"}:
        content = entry.get("content")
        message = entry.get("message")
        if (content in (None, "") or content == []) and isinstance(message, Mapping):
            content = message.get("content")
        role = "user" if entry_type == "user" else "assistant"
        return _message_from_text(role, _content_text(content)), False
    return None, False


def scan_transcript(path: Path) -> dict[str, Any]:
    """Hash the exact transcript snapshot and retain only safe UI messages."""

    digest = hashlib.sha256()
    messages: collections.deque[dict[str, str]] = collections.deque(
        maxlen=DEFAULT_MAX_MESSAGES
    )
    bytes_hashed = 0
    compaction_boundaries = 0
    parse_errors = 0
    fmt = "jsonl"
    if path.suffix.lower() == ".md":
        fmt = "markdown_segment"
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                bytes_hashed += len(chunk)
        return {
            "transcript_sha256": digest.hexdigest(),
            "transcript_bytes_hashed": bytes_hashed,
            "messages": [],
            "compaction_boundaries": 0,
            "parse_errors": 0,
            "format": fmt,
        }

    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            bytes_hashed += len(raw_line)
            # Avoid parsing pathological single-line blobs; they are never a
            # useful compact checkpoint and could exhaust a hook's memory.
            if len(raw_line) > 2_000_000:
                parse_errors += 1
                continue
            try:
                entry = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                parse_errors += 1
                continue
            if not isinstance(entry, Mapping):
                continue
            message, boundary = _completed_message(entry)
            if boundary:
                messages.clear()
                compaction_boundaries += 1
            elif message is not None:
                messages.append(message)

    return {
        "transcript_sha256": digest.hexdigest(),
        "transcript_bytes_hashed": bytes_hashed,
        "messages": list(messages),
        "compaction_boundaries": compaction_boundaries,
        "parse_errors": parse_errors,
        "format": fmt,
    }


def build_checkpoint(
    messages: Sequence[Mapping[str, str]],
    *,
    max_chars: int = DEFAULT_MAX_CHECKPOINT_CHARS,
) -> tuple[str, int, int]:
    """Render newest relevant messages within a strict character budget."""

    if max_chars < 512:
        raise ValueError("checkpoint budget must be at least 512 characters")
    selected_reversed: list[str] = []
    remaining = max_chars
    total_redactions = 0

    for message in reversed(messages):
        role = str(message.get("role") or "unknown").upper()
        phase = str(message.get("phase") or "").strip()
        label = f"[{role}{' ' + phase if phase else ''}]\n"
        text = str(message.get("text") or "")
        block = label + text
        try:
            total_redactions += int(message.get("redactions") or 0)
        except (TypeError, ValueError):
            pass
        separator_cost = 2 if selected_reversed else 0
        if len(block) + separator_cost <= remaining:
            selected_reversed.append(block)
            remaining -= len(block) + separator_cost
            continue
        if not selected_reversed and remaining > 96:
            marker = "\n[TRUNCATED CHECKPOINT MESSAGE]"
            selected_reversed.append(block[: remaining - len(marker)] + marker)
        break

    blocks = list(reversed(selected_reversed))
    if not blocks:
        return "[No completed user/assistant messages after the last compaction boundary.]", 0, 0
    return "\n\n".join(blocks), len(blocks), total_redactions


def _hash_regular_file(path: Path, max_bytes: int = 10_000_000) -> dict[str, Any] | None:
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return {"path": str(path), "bytes": info.st_size, "sha256": digest.hexdigest()}
    except OSError:
        return None


def project_fingerprint(cwd_value: Any) -> dict[str, Any]:
    """Capture content-free project pointers the next agent can verify."""

    cwd = Path(cwd_value if isinstance(cwd_value, str) and cwd_value else os.getcwd())
    try:
        cwd = cwd.expanduser().resolve()
    except OSError:
        cwd = Path(os.getcwd()).resolve()
    state_files: list[dict[str, Any]] = []
    for name in ("index.md", "INDEX.md"):
        item = _hash_regular_file(cwd / name)
        if item is not None:
            state_files.append(item)

    git_head = ""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--verify", "HEAD"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
            check=False,
        )
        candidate = result.stdout.strip().lower()
        if result.returncode == 0 and _HEX_HEAD_RE.fullmatch(candidate):
            git_head = candidate
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"cwd": str(cwd), "git_head": git_head or None, "state_files": state_files}


def spool_path_for(
    payload: Mapping[str, Any],
    *,
    spool_dir: Path | None = None,
    require_transcript: bool = True,
) -> tuple[Path, Path | None]:
    directory = (spool_dir or default_spool_dir()).expanduser().resolve()
    raw_transcript = payload.get("transcript_path")
    transcript = validate_transcript_path(raw_transcript) if raw_transcript else None
    if transcript is None and require_transcript:
        raise ValueError("hook payload has no transcript path")
    path_key = hashlib.sha256(str(transcript or "none").encode("utf-8")).hexdigest()[:16]
    filename = f"{_safe_id(payload.get('session_id'))}.{path_key}.json"
    return directory / filename, transcript


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    encoded = (json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    if len(encoded) > DEFAULT_MAX_SPOOL_BYTES:
        raise ValueError("continuity spool exceeds hard size limit")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        pass


def _read_regular_bytes(path: Path, *, max_bytes: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("continuity journal is not a regular file")
        if info.st_size < 0 or info.st_size > max_bytes:
            raise ValueError("continuity journal exceeds its hard size limit")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise OSError("continuity journal changed during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise OSError("continuity journal changed during read")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _journal_entry(record: Mapping[str, Any]) -> tuple[str, str]:
    checkpoint = record.get("checkpoint")
    checkpoint_sha = record.get("checkpoint_sha256")
    if not isinstance(checkpoint, str) or not isinstance(checkpoint_sha, str):
        raise ValueError("continuity record has no checkpoint")
    if hashlib.sha256(checkpoint.encode("utf-8")).hexdigest() != checkpoint_sha:
        raise ValueError("continuity checkpoint checksum mismatch")
    project = record.get("project") if isinstance(record.get("project"), Mapping) else {}
    source = record.get("source") if isinstance(record.get("source"), Mapping) else {}
    marker = f"{JOURNAL_ENTRY_PREFIX}{checkpoint_sha} -->"
    entry = (
        f"{marker}\n"
        f"## {record.get('captured_at') or 'unknown-time'} — Codex continuity\n\n"
        f"- Session: `{record.get('session_id') or 'unknown'}`\n"
        f"- Event: `{source.get('hook_event_name') or 'unknown'}` / "
        f"`{source.get('trigger') or 'unspecified'}`\n"
        f"- Project: `{project.get('cwd') or 'unknown'}`\n"
        f"- Transcript SHA-256: `{record.get('transcript_sha256') or 'unknown'}`\n"
        f"- Checkpoint SHA-256: `{checkpoint_sha}`\n\n"
        "### Latest completed user/assistant context\n\n"
        f"{checkpoint}\n"
        f"{JOURNAL_ENTRY_SUFFIX}\n"
    )
    return marker, entry


def append_journal_checkpoint(
    record: Mapping[str, Any],
    *,
    journal_path: Path | None = None,
) -> dict[str, Any]:
    """Atomically append one unique, redacted checkpoint to ``journal.md``.

    The local journal is committed before any MemPalace network attempt.  A
    deterministic checkpoint marker makes retries idempotent, while a lock and
    atomic replace keep concurrent root/subagent hooks from interleaving bytes.
    Existing manual journal content is preserved verbatim.
    """

    path = (journal_path or default_journal_path()).expanduser()
    if not path.is_absolute():
        raise ValueError("continuity journal path must be absolute")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker, entry = _journal_entry(record)
    # Lock file on the pod-local overlay, keyed by the target (stale-network-flock,
    # 2026-08-22: a lock beside the target on /workspace outlives a dead pod).
    lock_path = pod_local_lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if path.exists() or path.is_symlink():
            existing = _read_regular_bytes(path, max_bytes=DEFAULT_MAX_JOURNAL_BYTES)
        else:
            existing = b"# Codex Continuity Journal\n\n"
        marker_bytes = marker.encode("utf-8")
        if marker_bytes in existing:
            return {
                "status": "journal_unchanged",
                "journal_path": str(path),
                "checkpoint_sha256": record.get("checkpoint_sha256"),
                "journal_bytes": len(existing),
                "journal_sha256": hashlib.sha256(existing).hexdigest(),
            }
        separator = b"" if existing.endswith(b"\n\n") else (b"\n" if existing.endswith(b"\n") else b"\n\n")
        updated = existing + separator + entry.encode("utf-8") + b"\n"
        if len(updated) > DEFAULT_MAX_JOURNAL_BYTES:
            raise ValueError("continuity journal exceeds its hard size limit")
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            temp_name = ""
            os.chmod(path, 0o600)
            _fsync_directory(path.parent)
        finally:
            if temp_name:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
        return {
            "status": "journal_appended",
            "journal_path": str(path),
            "checkpoint_sha256": record.get("checkpoint_sha256"),
            "journal_entry_sha256": hashlib.sha256(entry.encode("utf-8")).hexdigest(),
            "journal_bytes": len(updated),
            "journal_sha256": hashlib.sha256(updated).hexdigest(),
        }
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def pending_path_for(latest_path: Path, record: Mapping[str, Any]) -> Path:
    """Return the immutable retry-queue path for one checkpoint."""

    checkpoint_sha = record.get("checkpoint_sha256")
    if not isinstance(checkpoint_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha):
        raise ValueError("continuity checkpoint has an invalid checksum")
    pending_dir = latest_path.parent / "pending"
    return pending_dir / f"{latest_path.stem}.{checkpoint_sha}.json"


def _queue_pending_record(latest_path: Path, record: Mapping[str, Any]) -> Path:
    pending_path = pending_path_for(latest_path, record)
    existing = _read_record(pending_path) if pending_path.exists() else None
    if existing is None:
        _atomic_write_json(pending_path, record)
    elif existing.get("checkpoint_sha256") != record.get("checkpoint_sha256"):
        raise ValueError("pending continuity checkpoint identity mismatch")
    return pending_path


def capture_precompact(
    payload: Mapping[str, Any],
    *,
    spool_dir: Path | None = None,
    captured_at: str | None = None,
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    """Create one atomic pending checkpoint for a PreCompact event."""

    path, transcript = spool_path_for(payload, spool_dir=spool_dir)
    assert transcript is not None
    scan = scan_transcript(transcript)
    artifacts = list_session_memory_files(transcript)
    pointer = render_file_pointers(artifacts)
    checkpoint, used, redactions = build_checkpoint(scan.pop("messages"))
    if pointer:
        checkpoint = pointer + "\n\n" + checkpoint
    checkpoint_sha = hashlib.sha256(checkpoint.encode("utf-8")).hexdigest()
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "storage": "continuity_spool",
        "captured_at": captured_at or _utc_now(),
        "session_id": str(payload.get("session_id") or ""),
        "turn_id": str(payload.get("turn_id") or ""),
        "source": {
            "hook_event_name": str(payload.get("hook_event_name") or "PreCompact"),
            "trigger": str(payload.get("trigger") or ""),
            "agent_id": str(payload.get("agent_id") or ""),
            "agent_type": str(payload.get("agent_type") or ""),
        },
        "transcript_path": str(transcript),
        "transcript_sha256": scan["transcript_sha256"],
        "transcript_bytes_hashed": scan["transcript_bytes_hashed"],
        "memory_files": artifacts,
        "project": project_fingerprint(payload.get("cwd")),
        "checkpoint": checkpoint,
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_chars": len(checkpoint),
        "messages_used": used,
        "redactions": redactions,
        "compaction_boundaries": scan["compaction_boundaries"],
        "parse_errors": scan["parse_errors"],
        "palace_reconciled": False,
        "palace_reconciled_at": None,
        "palace_entry_id": None,
        "palace_transport": None,
    }
    _atomic_write_json(path, record)
    receipt = {
        "status": "spooled",
        "spool_file": path.name,
        "session_id": _safe_id(payload.get("session_id")),
        "transcript_sha256": record["transcript_sha256"],
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_chars": len(checkpoint),
        "messages_used": used,
        "redactions": redactions,
        "palace_reconciled": False,
    }
    return record, path, receipt


def _read_record(path: Path) -> dict[str, Any] | None:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            return None
        if info.st_size <= 0 or info.st_size > DEFAULT_MAX_SPOOL_BYTES:
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
        return None
    checkpoint = record.get("checkpoint")
    expected = record.get("checkpoint_sha256")
    if not isinstance(checkpoint, str) or not isinstance(expected, str):
        return None
    if hashlib.sha256(checkpoint.encode("utf-8")).hexdigest() != expected:
        return None
    return record


def load_for_session_start(
    payload: Mapping[str, Any],
    *,
    spool_dir: Path | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Load only the checkpoint matching this session and transcript path."""

    receipt: dict[str, Any] = {"status": "not_found", "spool_file": ""}
    try:
        path, transcript = spool_path_for(payload, spool_dir=spool_dir)
    except (OSError, ValueError):
        receipt["status"] = "invalid_hook_path"
        return None, receipt
    record = _read_record(path)
    if record is None:
        return None, receipt
    if record.get("session_id") != str(payload.get("session_id") or ""):
        receipt["status"] = "session_mismatch"
        return None, receipt
    if record.get("transcript_path") != str(transcript):
        receipt["status"] = "transcript_mismatch"
        return None, receipt
    receipt.update(
        status="loaded",
        spool_file=path.name,
        checkpoint_sha256=record.get("checkpoint_sha256"),
        checkpoint_chars=record.get("checkpoint_chars"),
        palace_reconciled=bool(record.get("palace_reconciled")),
    )
    return record, receipt


def render_for_model(record: Mapping[str, Any], *, max_chars: int = 6_500) -> str:
    """Render a verified spool record with an explicit storage provenance."""

    checkpoint = str(record.get("checkpoint") or "")
    source = record.get("source") if isinstance(record.get("source"), Mapping) else {}
    project = record.get("project") if isinstance(record.get("project"), Mapping) else {}
    state_files = project.get("state_files") if isinstance(project.get("state_files"), Sequence) else []
    state_lines = []
    for item in state_files[:4]:
        if isinstance(item, Mapping):
            state_lines.append(
                f"- {item.get('path')} bytes={item.get('bytes')} sha256={item.get('sha256')}"
            )
    provenance = "palace+spool" if record.get("palace_reconciled") else "spool-only (pending palace reconciliation)"
    header = (
        "<mempalace-continuity-spool>\n"
        "Sanitized deterministic lifecycle checkpoint. Tool I/O, reasoning, system/developer "
        "messages, and injected environment blocks were excluded. Verify mutable files locally.\n"
        f"storage: {provenance}\n"
        f"captured_at: {record.get('captured_at')}\n"
        f"session_id: {record.get('session_id')}\n"
        f"source: {source.get('hook_event_name')}:{source.get('trigger')}\n"
        f"transcript_path: {record.get('transcript_path')}\n"
        f"transcript_sha256: {record.get('transcript_sha256')}\n"
        f"checkpoint_sha256: {record.get('checkpoint_sha256')}\n"
        f"project_cwd: {project.get('cwd')}\n"
        f"git_head: {project.get('git_head')}\n"
    )
    if state_lines:
        header += "project_state_files:\n" + "\n".join(state_lines) + "\n"
    body_prefix = "checkpoint:\n"
    footer = "\n</mempalace-continuity-spool>"
    remaining = max_chars - len(header) - len(body_prefix) - len(footer)
    if remaining < 128:
        raise ValueError("model spool budget is too small")
    if len(checkpoint) > remaining:
        marker = "\n[TRUNCATED FOR SESSIONSTART INJECTION]"
        checkpoint = checkpoint[: remaining - len(marker)] + marker
    return header + body_prefix + checkpoint + footer


def _palace_entry(record: Mapping[str, Any]) -> str:
    return (
        "CODEX_PRECOMPACT_CONTINUITY_V1\n"
        f"spool_id:{record.get('checkpoint_sha256')}\n"
        f"captured_at:{record.get('captured_at')}\n"
        f"session_id:{record.get('session_id')}\n"
        f"transcript_sha256:{record.get('transcript_sha256')}\n"
        f"source:{json.dumps(record.get('source') or {}, sort_keys=True)}\n"
        f"project:{json.dumps(record.get('project') or {}, sort_keys=True)}\n"
        "checkpoint:\n"
        f"{record.get('checkpoint') or ''}"
    )


def _write_via_http_hub(record: Mapping[str, Any], palace_path: str) -> dict[str, Any] | None:
    """Use a registered HTTP MCP owner; return None when none is live."""

    from mempalace import server_registry

    info = server_registry.read_live_serverinfo(palace_path)
    if not info or info.get("read_only"):
        return None
    base_url = server_registry.client_base_url(info)
    headers = {"Content-Type": "application/json"}
    token = server_registry.load_server_token(palace_path)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "mempalace_diary_write",
                "arguments": {
                    "agent_name": "codex",
                    "entry": _palace_entry(record),
                    "topic": "precompact_continuity",
                    "wing": "",
                },
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(f"{base_url}/mcp", data=body, headers=headers)
    try:
        # Local journal/spool durability is already committed.  Bound this
        # optional hub reconciliation tightly so it cannot consume Codex's
        # 20-second PreCompact budget and prevent the hook receipt from landing.
        with urllib.request.urlopen(request, timeout=4.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return {"success": False, "status": "http_hub_failed"}
    if payload.get("error"):
        return {"success": False, "status": "http_hub_refused"}
    try:
        result = json.loads(payload["result"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError):
        return {"success": False, "status": "http_hub_bad_response"}
    return {
        "success": bool(result.get("success")),
        "status": "reconciled" if result.get("success") else "http_hub_write_failed",
        "transport": "http_hub",
        "entry_id": result.get("entry_id"),
    }


def reconcile_path(
    path: Path,
    *,
    writer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconcile one verified pending checkpoint and atomically mark success."""

    record = _read_record(path)
    if record is None:
        return {"status": "invalid_spool", "spool_file": path.name}
    if record.get("palace_reconciled"):
        return {"status": "already_reconciled", "spool_file": path.name}

    if writer is not None:
        result = dict(writer(record))
    else:
        try:
            from mempalace.config import MempalaceConfig

            palace_path = MempalaceConfig().palace_path
            result = _write_via_http_hub(record, palace_path) or {
                "success": False,
                "status": "http_hub_unavailable",
            }
        except Exception:
            result = {"success": False, "status": "reconcile_unavailable"}

    if not result.get("success"):
        return {
            "status": result.get("status") or "reconcile_failed",
            "spool_file": path.name,
            "checkpoint_sha256": record.get("checkpoint_sha256"),
        }
    record.update(
        palace_reconciled=True,
        palace_reconciled_at=_utc_now(),
        palace_entry_id=result.get("entry_id"),
        palace_transport=result.get("transport") or "injected_writer",
    )
    _atomic_write_json(path, record)
    return {
        "status": "reconciled",
        "spool_file": path.name,
        "checkpoint_sha256": record.get("checkpoint_sha256"),
        "palace_entry_id": record.get("palace_entry_id"),
        "palace_transport": record.get("palace_transport"),
    }


def reconcile_pending(
    *,
    spool_dir: Path | None = None,
    limit: int = DEFAULT_RECONCILE_LIMIT,
) -> list[dict[str, Any]]:
    """Try a bounded number of pending files without ever waiting on a writer."""

    directory = (spool_dir or default_spool_dir()).expanduser().resolve()
    try:
        candidates = sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime)
    except OSError:
        return []
    receipts: list[dict[str, Any]] = []
    for path in candidates:
        record = _read_record(path)
        if record is None or record.get("palace_reconciled"):
            continue
        receipts.append(reconcile_path(path))
        if len(receipts) >= max(0, limit):
            break
    return receipts
