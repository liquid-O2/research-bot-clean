"""Versioned lossless tape for Grok compaction.

Grok compaction summaries are not the memory. Compaction segment_*.md files
are truncated at 512 KiB. chat_history.jsonl is rewritten on compact.
updates.jsonl plus the incremental tails are the complete ACP log.

This module stores unique file bytes under by_hash/ so a later compact cannot
overwrite an earlier snapshot. Never opens a second Chroma writer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .mempalace_continuity_spool import DEFAULT_HOOK_STATE_DIR
except ImportError:
    from mempalace_continuity_spool import DEFAULT_HOOK_STATE_DIR  # type: ignore


_USER_QUERY_RE = re.compile(
    r"<user_query>\s*(.*?)\s*</user_query>",
    re.IGNORECASE | re.DOTALL,
)
MAX_UPDATES_COPY_BYTES = 16_000_000
MAX_USER_QUERY_CHARS = 32_000
SEGMENT_TRUNCATION_MARK = "TRUNCATED at 524288"


def hook_state_dir() -> Path:
    override = os.environ.get("MEMPALACE_HOOK_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return DEFAULT_HOOK_STATE_DIR


def sources_root() -> Path:
    override = os.environ.get("MEMPALACE_SOURCES_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    return Path("/workspace/.mempalace/sources")


def grok_sessions_root() -> Path:
    override = os.environ.get("MEMPALACE_GROK_SESSIONS_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".grok" / "sessions"


def recall_path() -> Path:
    return hook_state_dir() / "RECALL.md"


def ledger_path() -> Path:
    return hook_state_dir() / "COMPACTION_LEDGER.jsonl"


def needs_recall_path() -> Path:
    return hook_state_dir() / "NEEDS_RECALL"


def verbatim_log_path() -> Path:
    return hook_state_dir() / "VERBATIM_USER_LOG.md"


def conversation_tape_path() -> Path:
    return hook_state_dir() / "CONVERSATION_TAPE.jsonl"


def conversation_hash_path() -> Path:
    return hook_state_dir() / "CONVERSATION_TAPE.hashes"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def hash_regular_file(path: Path) -> dict[str, Any] | None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            return None
        digest = hashlib.sha256()
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    finally:
        os.close(fd)
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
        "bytes": info.st_size,
    }


def store_by_hash(source: Path, dest_root: Path) -> dict[str, Any]:
    """Copy source to dest_root/by_hash/<sha256>_<name>. Same hash is a no-op."""
    source = source.expanduser()
    hashed = hash_regular_file(source)
    if hashed is None:
        return {"source": str(source), "status": "missing"}
    dest_root = dest_root.expanduser()
    by_hash = dest_root / "by_hash"
    by_hash.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = by_hash / f"{hashed['sha256']}_{source.name}"
    if dest.is_file():
        return {
            "source": str(source),
            "archive": str(dest),
            "sha256": hashed["sha256"],
            "bytes": hashed["bytes"],
            "status": "exists",
            "truncated_segment": _looks_truncated(source),
        }
    src_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{dest.name}.", dir=by_hash)
        try:
            os.fchmod(fd, 0o600)
            remaining = hashed["bytes"]
            while remaining:
                chunk = os.read(src_fd, min(1024 * 1024, remaining))
                if not chunk:
                    raise OSError("source truncated during hash copy")
                os.write(fd, chunk)
                remaining -= len(chunk)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp_name, dest)
        os.chmod(dest, 0o600)
    finally:
        os.close(src_fd)
    return {
        "source": str(source),
        "archive": str(dest),
        "sha256": hashed["sha256"],
        "bytes": hashed["bytes"],
        "status": "copied",
        "truncated_segment": _looks_truncated(source),
    }


def _looks_truncated(path: Path) -> bool:
    if not path.name.startswith("segment_") or path.suffix.lower() != ".md":
        return False
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 512))
            tail = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    return SEGMENT_TRUNCATION_MARK in tail or size >= 524288


def is_nested_grok_session(session_id: str) -> bool:
    """True when this session_id lives under another session's subagents/."""
    if not session_id:
        return False
    root = grok_sessions_root()
    if not root.is_dir():
        return False
    try:
        groups = list(root.iterdir())
    except OSError:
        return False
    for group in groups:
        if not group.is_dir():
            continue
        try:
            sessions = list(group.iterdir())
        except OSError:
            continue
        for sess in sessions:
            if sess.name == session_id:
                continue
            if (sess / "subagents" / session_id).exists():
                return True
    return False


def session_dir_from_transcript(transcript_path: str | os.PathLike[str] | None) -> Path | None:
    if not transcript_path:
        return None
    path = Path(str(transcript_path)).expanduser()
    if path.is_file():
        path = path.parent
    if not path.is_dir():
        return None
    if (path / "chat_history.jsonl").is_file() or (path / "updates.jsonl").is_file():
        return path
    return path if path.is_dir() else None


def snapshot_session(
    session_dir: Path,
    *,
    event: str,
    session_id: str = "",
) -> dict[str, Any]:
    """Hash-copy chat_history, compaction files, and small updates.jsonl."""
    session_dir = session_dir.expanduser().resolve()
    sid = session_id or session_dir.name
    dest_root = sources_root() / "grok" / sid
    dest_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored: list[dict[str, Any]] = []
    chat = session_dir / "chat_history.jsonl"
    if chat.is_file():
        stored.append(store_by_hash(chat, dest_root))
    compact = session_dir / "compaction"
    if compact.is_dir():
        for path in sorted(compact.iterdir()):
            if path.is_file() and path.suffix.lower() in {".md", ".json"}:
                stored.append(store_by_hash(path, dest_root))
    updates = session_dir / "updates.jsonl"
    if updates.is_file():
        info = hash_regular_file(updates)
        if info and info["bytes"] <= MAX_UPDATES_COPY_BYTES:
            stored.append(store_by_hash(updates, dest_root))
        elif info:
            stored.append(
                {
                    "source": str(updates),
                    "sha256": info["sha256"],
                    "bytes": info["bytes"],
                    "status": "skipped_large",
                    "note": "use hook_state/tails incremental copies",
                }
            )
    receipt = {
        "captured_at": _utc_now(),
        "event": event,
        "session_id": sid,
        "session_dir": str(session_dir),
        "files": stored,
    }
    receipt_path = dest_root / "generations.jsonl"
    receipt_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with receipt_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return receipt


def append_ledger(row: Mapping[str, Any]) -> Path:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = dict(row)
    payload.setdefault("captured_at", _utc_now())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def write_recall_index(
    *,
    session_id: str,
    session_dir: Path | None,
    snapshot: Mapping[str, Any] | None = None,
) -> Path:
    lines = [
        "# Compaction recall — lossless tape",
        "",
        "Compaction **summaries are not the memory**. Grok `segment_*.md` files",
        "are truncated at 512 KiB (`TRUNCATED at 524288 bytes`). `chat_history.jsonl`",
        "is rewritten on compact. Do not answer from the compact summary.",
        "",
        "Read these, in order, after every compact:",
        "",
        "1. This file.",
        "2. Every `chat_history` by_hash snapshot listed below — **full turns**:",
        "   user, assistant replies, reasoning summaries, and tool calls.",
        "   That is the thoughts tape. User-only logs are not sufficient.",
        "3. `CONVERSATION_TAPE.jsonl` — grepable user + assistant + reasoning summaries.",
        "4. Live `compaction/INDEX.md` then each `segment_*.md` (truncated at 512KiB).",
        "5. `updates.jsonl` tails under `hook_state/tails/` (tool results).",
        "6. `VERBATIM_USER_LOG.md` is a user-word index only, not the memory.",
        "",
        "MemPalace search, Grok `/flush`, `/dream`, and the 6k journal checkpoint are indexes,",
        "not the tape.",
        "",
        f"- written_at: `{_utc_now()}`",
        f"- session_id: `{session_id}`",
    ]
    if session_dir is not None:
        lines.append(f"- live_session_dir: `{session_dir}`")
        index = session_dir / "compaction" / "INDEX.md"
        if index.is_file():
            hashed = hash_regular_file(index)
            if hashed:
                lines.append(
                    f"- live_index: `{hashed['path']}` sha256=`{hashed['sha256']}` "
                    f"bytes=`{hashed['bytes']}`"
                )
        compact = session_dir / "compaction"
        if compact.is_dir():
            for segment in sorted(compact.glob("segment_*.md")):
                hashed = hash_regular_file(segment)
                if not hashed:
                    continue
                flag = " TRUNCATED" if _looks_truncated(segment) else ""
                lines.append(
                    f"- live_segment: `{hashed['path']}` sha256=`{hashed['sha256']}` "
                    f"bytes=`{hashed['bytes']}`{flag}"
                )
        chat = session_dir / "chat_history.jsonl"
        if chat.is_file():
            hashed = hash_regular_file(chat)
            if hashed:
                lines.append(
                    f"- live_chat_history: `{hashed['path']}` sha256=`{hashed['sha256']}` "
                    f"bytes=`{hashed['bytes']}` (post-compact; older turns are in by_hash snapshots)"
                )
        updates = session_dir / "updates.jsonl"
        if updates.is_file():
            hashed = hash_regular_file(updates)
            if hashed:
                lines.append(
                    f"- live_updates: `{hashed['path']}` sha256=`{hashed['sha256']}` "
                    f"bytes=`{hashed['bytes']}`"
                )
    tails = hook_state_dir() / "tails"
    if session_id and tails.is_dir():
        lines.extend(["", "## Incremental updates.jsonl tails (lossless ACP prefix)", ""])
        for tail in sorted(tails.glob(f"{session_id}.*.jsonl")):
            hashed = hash_regular_file(tail)
            if hashed:
                lines.append(
                    f"- tail `{hashed['path']}` sha256=`{hashed['sha256']}` "
                    f"bytes=`{hashed['bytes']}`"
                )
    if snapshot:
        lines.extend(["", "## Latest hash-addressed snapshots (never overwritten)", ""])
        for row in snapshot.get("files") or []:
            if not isinstance(row, Mapping):
                continue
            archive = row.get("archive") or ""
            status = row.get("status")
            trunc = " TRUNCATED_SEGMENT" if row.get("truncated_segment") else ""
            lines.append(
                f"- `{archive or row.get('source')}` sha256=`{row.get('sha256')}` "
                f"bytes=`{row.get('bytes')}` status=`{status}`{trunc}"
            )
    dest = recall_path()
    text = "\n".join(lines) + "\n"
    _atomic_write(dest, text.encode("utf-8"))
    return dest


def grok_memory_path() -> Path:
    override = os.environ.get("MEMPALACE_GROK_MEMORY_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".grok" / "memory" / "MEMORY.md"


def write_grok_memory_pointer() -> Path:
    dest = grok_memory_path()
    text = (
        "# Entry V2 continuity (pointers, not a summary)\n\n"
        "Compaction summaries are not the memory. After every compact read:\n\n"
        f"1. `{recall_path()}`\n"
        f"2. `{conversation_tape_path()}` (user + assistant + reasoning summaries)\n"
        f"3. by_hash `chat_history.jsonl` snapshots listed in RECALL.md (full thoughts + tool calls)\n"
        f"4. `{ledger_path()}`\n\n"
        "User-only logs are not the memory. Grok `/flush` and `/dream` are LLM summaries. "
        "Hidden chain-of-thought may be encrypted on disk; we keep plaintext assistant "
        "replies and reasoning summaries plus the raw jsonl snapshot. "
        "Neural is dead. Tabular CatBoost. 2025H2 sealed.\n"
    )
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _atomic_write(dest, text.encode("utf-8"))
    return dest


def set_needs_recall(session_id: str) -> Path:
    path = needs_recall_path()
    payload = {
        "session_id": session_id,
        "set_at": _utc_now(),
        "recall_path": str(recall_path()),
    }
    _atomic_write(path, (json.dumps(payload) + "\n").encode("utf-8"))
    return path


def clear_needs_recall() -> None:
    path = needs_recall_path()
    try:
        if path.is_file() and not path.is_symlink():
            path.unlink()
    except OSError:
        pass


def needs_recall_record() -> dict[str, Any] | None:
    path = needs_recall_path()
    try:
        if not path.is_file() or path.is_symlink():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def extract_user_queries(text: str) -> list[str]:
    found: list[str] = []
    for match in _USER_QUERY_RE.finditer(text or ""):
        body = match.group(1).strip()
        if not body or len(body) > MAX_USER_QUERY_CHARS:
            continue
        if "<user_info>" in body or "<work_policy>" in body or "synthetic_reason" in body:
            continue
        if body not in found:
            found.append(body)
    return found


def _text_from_user_obj(obj: Mapping[str, Any]) -> str:
    if obj.get("synthetic_reason") == "compaction_meta":
        return ""
    content = obj.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(parts)
    return ""


def append_verbatim_users(texts: list[str], *, session_id: str, source: str) -> int:
    if not texts:
        return 0
    path = verbatim_log_path()
    existing = ""
    if path.is_file():
        existing = path.read_text(encoding="utf-8", errors="replace")
    added = 0
    chunks: list[str] = []
    for text in texts:
        text = text.strip()
        if not text or text in existing:
            continue
        if any(text == chunk for chunk in chunks):
            continue
        chunks.append(
            f"\n## { _utc_now() } session=`{session_id}` source=`{source}`\n\n{text}\n"
        )
        added += 1
    if not added:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    header = ""
    if not path.is_file():
        header = (
            "# Verbatim user words (append-only, not a summary)\n\n"
            "These are exact `<user_query>` bodies. Do not paraphrase them.\n"
        )
    with path.open("a", encoding="utf-8") as handle:
        if header:
            handle.write(header)
        for chunk in chunks:
            handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    return added


def harvest_user_queries_from_jsonl(path: Path, *, session_id: str) -> int:
    added = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line or "<user_query>" not in line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    added += append_verbatim_users(
                        extract_user_queries(line),
                        session_id=session_id,
                        source=str(path),
                    )
                    continue
                if not isinstance(obj, dict) or obj.get("type") != "user":
                    continue
                added += append_verbatim_users(
                    extract_user_queries(_text_from_user_obj(obj)),
                    session_id=session_id,
                    source=str(path),
                )
    except OSError:
        return added
    return added


def harvest_user_queries_from_session(session_dir: Path, *, session_id: str) -> int:
    added = 0
    chat = session_dir / "chat_history.jsonl"
    if chat.is_file():
        added += harvest_user_queries_from_jsonl(chat, session_id=session_id)
    added += harvest_conversation_from_session(
        session_dir, session_id=session_id, include_snapshots=False
    )
    return added


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(parts).strip()
    return ""


def _reasoning_summary(obj: Mapping[str, Any]) -> str:
    summary = obj.get("summary")
    if not isinstance(summary, list):
        return ""
    parts: list[str] = []
    for item in summary:
        if isinstance(item, Mapping) and str(item.get("type") or "") == "summary_text":
            text = str(item.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _load_tape_hashes() -> set[str]:
    path = conversation_hash_path()
    if not path.is_file():
        return set()
    try:
        return {
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        }
    except OSError:
        return set()


def append_conversation_turns(turns: list[dict[str, str]]) -> int:
    if not turns:
        return 0
    seen = _load_tape_hashes()
    tape = conversation_tape_path()
    hashes = conversation_hash_path()
    tape.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    added = 0
    new_hash_lines: list[str] = []
    with tape.open("a", encoding="utf-8") as handle:
        for turn in turns:
            role = str(turn.get("role") or "")
            text = str(turn.get("text") or "").strip()
            if not role or not text or len(text) > MAX_USER_QUERY_CHARS:
                continue
            digest = hashlib.sha256(f"{role}\n{text}".encode("utf-8")).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            record = {
                "captured_at": _utc_now(),
                "role": role,
                "session_id": turn.get("session_id") or "",
                "source": turn.get("source") or "",
                "text": text,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            new_hash_lines.append(digest)
            added += 1
        if added:
            handle.flush()
            os.fsync(handle.fileno())
    if new_hash_lines:
        with hashes.open("a", encoding="utf-8") as handle:
            for digest in new_hash_lines:
                handle.write(digest + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return added


def harvest_conversation_from_jsonl(path: Path, *, session_id: str) -> int:
    turns: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                kind = str(obj.get("type") or "")
                source = str(path)
                if kind == "user":
                    if obj.get("synthetic_reason") == "compaction_meta":
                        continue
                    body = _content_text(obj.get("content"))
                    queries = extract_user_queries(body)
                    text = queries[0] if queries else body
                    if text and "<user_info>" not in text and "<work_policy>" not in text:
                        turns.append(
                            {
                                "role": "user",
                                "text": text,
                                "session_id": session_id,
                                "source": source,
                            }
                        )
                elif kind == "assistant":
                    text = _content_text(obj.get("content"))
                    if text:
                        turns.append(
                            {
                                "role": "assistant",
                                "text": text,
                                "session_id": session_id,
                                "source": source,
                            }
                        )
                elif kind == "reasoning":
                    text = _reasoning_summary(obj)
                    if text:
                        turns.append(
                            {
                                "role": "reasoning",
                                "text": text,
                                "session_id": session_id,
                                "source": source,
                            }
                        )
    except OSError:
        return 0
    return append_conversation_turns(turns)


def harvest_conversation_from_session(
    session_dir: Path, *, session_id: str, include_snapshots: bool = False
) -> int:
    added = 0
    chat = session_dir / "chat_history.jsonl"
    if chat.is_file():
        added += harvest_conversation_from_jsonl(chat, session_id=session_id)
    if include_snapshots:
        dest_root = sources_root() / "grok" / session_id / "by_hash"
        if dest_root.is_dir():
            for snap in sorted(dest_root.glob("*_chat_history.jsonl")):
                added += harvest_conversation_from_jsonl(snap, session_id=session_id)
    return added
