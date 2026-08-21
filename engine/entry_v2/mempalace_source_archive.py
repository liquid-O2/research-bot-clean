"""Copy Grok/Claude/Codex transcripts into /workspace/.mempalace/sources.

The live files under ~/.grok, ~/.claude, and ~/.codex remain authoritative
while they exist.  These copies survive rotation and are what the palace
miner is allowed to read.  Never opens a second Chroma writer.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mempalace_continuity_spool import (
    DEFAULT_HOOK_STATE_DIR,
    _hash_regular_file,
    list_session_memory_files,
)
from .mempalace_lossless_tape import sources_root, store_by_hash


SOURCES_ROOT = Path("/workspace/.mempalace/sources")
MANIFEST_PATH = DEFAULT_HOOK_STATE_DIR / "TRANSCRIPT_MANIFEST.md"


def _sources_root() -> Path:
    return sources_root()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _copy_file(source: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    src_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(src_fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"not a regular file: {source}")
        digest = hashlib.sha256()
        fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        try:
            os.fchmod(fd, 0o600)
            remaining = info.st_size
            while remaining:
                chunk = os.read(src_fd, min(1024 * 1024, remaining))
                if not chunk:
                    raise OSError("source truncated during archive copy")
                os.write(fd, chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp_name, destination)
        os.chmod(destination, 0o600)
    finally:
        os.close(src_fd)
    return {
        "source": str(source),
        "archive": str(destination),
        "sha256": digest.hexdigest(),
        "bytes": info.st_size,
    }


def _copy_preserving(source: Path, destination: Path, dest_root: Path) -> list[dict[str, Any]]:
    """Keep unique bytes under by_hash/, then refresh the convenience path."""
    rows: list[dict[str, Any]] = []
    if destination.is_file() and destination.resolve() != source.resolve():
        rows.append(store_by_hash(destination, dest_root))
    rows.append(store_by_hash(source, dest_root))
    rows.append(_copy_file(source, destination))
    return rows


def archive_grok_session(session_dir: Path) -> list[dict[str, Any]]:
    session_dir = session_dir.expanduser().resolve()
    session_id = session_dir.name
    dest_root = _sources_root() / "grok" / session_id
    dest_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    copied: list[dict[str, Any]] = []
    chat = session_dir / "chat_history.jsonl"
    if chat.is_file():
        copied.extend(_copy_preserving(chat, dest_root / "chat_history.jsonl", dest_root))
        for item in list_session_memory_files(chat):
            src = Path(str(item["path"]))
            rel = src.name if src.parent.name != "compaction" else Path("compaction") / src.name
            target = dest_root / rel
            if src.resolve() != chat.resolve():
                copied.extend(_copy_preserving(src, target, dest_root))
    compact = session_dir / "compaction"
    if compact.is_dir():
        (dest_root / "compaction").mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in sorted(compact.iterdir()):
            if path.is_file() and path.suffix.lower() in {".md", ".json"}:
                already = any(
                    Path(str(row.get("source") or "")).resolve() == path.resolve()
                    for row in copied
                    if row.get("source")
                )
                if not already:
                    copied.extend(
                        _copy_preserving(path, dest_root / "compaction" / path.name, dest_root)
                    )
    receipt = dest_root / "archive.receipt.json"
    payload = {
        "captured_at": _utc_now(),
        "session_dir": str(session_dir),
        "files": copied,
    }
    receipt.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.chmod(receipt, 0o600)
    return copied


def write_transcript_manifest(
    *,
    grok_rows: Sequence[Mapping[str, Any]] | None = None,
) -> Path:
    lines = [
        "# Transcript manifest",
        "",
        f"- captured_at: `{_utc_now()}`",
        "",
        "Live transcripts and compaction segments are the memory. ",
        "Palace drawers and journal.md are indexes/pointers, not replacements.",
        "",
        "## Grok (this host)",
        "",
    ]
    grok_sessions = Path.home() / ".grok" / "sessions"
    if grok_sessions.is_dir():
        for chat in sorted(grok_sessions.rglob("chat_history.jsonl")):
            item = _hash_regular_file(chat, max_bytes=50_000_000)
            if item:
                lines.append(
                    f"- live `{item['path']}` sha256={item['sha256']} bytes={item['bytes']}"
                )
            compact = chat.parent / "compaction" / "INDEX.md"
            if compact.is_file():
                citem = _hash_regular_file(compact, max_bytes=50_000_000)
                if citem:
                    lines.append(
                        f"- compact-index `{citem['path']}` sha256={citem['sha256']} bytes={citem['bytes']}"
                    )
            for segment in sorted((chat.parent / "compaction").glob("segment_*.md")):
                sitem = _hash_regular_file(segment, max_bytes=50_000_000)
                if sitem:
                    lines.append(
                        f"- compact-segment `{sitem['path']}` sha256={sitem['sha256']} bytes={sitem['bytes']}"
                    )
    if grok_rows:
        lines.extend(["", "## Archived Grok copies", ""])
        for row in grok_rows:
            lines.append(
                f"- `{row.get('archive')}` from `{row.get('source')}` "
                f"sha256={row.get('sha256')} bytes={row.get('bytes')}"
            )
    lines.extend(["", "## Codex archives", ""])
    codex = _sources_root() / "codex"
    if codex.is_dir():
        for path in sorted(codex.glob("*.jsonl")):
            item = _hash_regular_file(path, max_bytes=50_000_000)
            if item:
                lines.append(
                    f"- `{item['path']}` sha256={item['sha256']} bytes={item['bytes']}"
                )
    lines.extend(["", "## Claude live JSONL (session files, not subagents)", ""])
    claude = Path.home() / ".claude" / "projects"
    if claude.is_dir():
        for project in sorted(claude.iterdir()):
            if not project.is_dir():
                continue
            for path in sorted(project.glob("*.jsonl")):
                item = _hash_regular_file(path, max_bytes=50_000_000)
                if item and int(item["bytes"]) > 256:
                    lines.append(
                        f"- `{item['path']}` sha256={item['sha256']} bytes={item['bytes']}"
                    )
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(MANIFEST_PATH, 0o600)
    return MANIFEST_PATH
