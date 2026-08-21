#!/usr/bin/env python3
"""Archive Grok/Claude/Codex transcripts and refresh continuity pointers.

Does not open a second Chroma writer. Palace writes go through the HTTP hub.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.entry_v2.mempalace_hub_client import call_tool
from engine.entry_v2.mempalace_lifecycle_hook import normalize_payload, write_continuity_latest
from engine.entry_v2.mempalace_continuity_spool import (
    append_journal_checkpoint,
    capture_precompact,
)
from engine.entry_v2.mempalace_source_archive import (
    archive_grok_session,
    write_transcript_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grok-session-dir", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--mine-diary", action="store_true")
    args = parser.parse_args()

    session_dir = Path(args.grok_session_dir).expanduser() if args.grok_session_dir else None
    if session_dir is None:
        sid = args.session_id or "01a02080-fe17-7770-9acb-9f741d73d633"
        candidate = Path.home() / ".grok" / "sessions" / "%2Fworkspace" / sid
        session_dir = candidate if candidate.is_dir() else None
        if session_dir is None:
            root = Path.home() / ".grok" / "sessions"
            matches = list(root.rglob(sid)) if sid else []
            session_dir = matches[0] if matches and matches[0].is_dir() else None
    if session_dir is None or not session_dir.is_dir():
        print("grok session dir not found", file=sys.stderr)
        return 2

    copied = archive_grok_session(session_dir)
    manifest = write_transcript_manifest(grok_rows=copied)
    chat = session_dir / "chat_history.jsonl"
    payload = {
        "hookEventName": "PreCompact",
        "sessionId": session_dir.name,
        "transcriptPath": str(chat) if chat.is_file() else str(session_dir / "compaction" / "INDEX.md"),
        "cwd": "/workspace",
        "trigger": "manual_archive",
    }
    payload = normalize_payload(payload)
    record, spool_path, receipt = capture_precompact(payload)
    journal = append_journal_checkpoint(record)
    latest = write_continuity_latest(record)
    diary = {"success": False, "status": "skipped"}
    if args.mine_diary:
        entry = (
            "GROK compact archive. Authoritative files, not a summary:\n"
            + "\n".join(
                f"{row.get('archive')} sha256={row.get('sha256')} bytes={row.get('bytes')}"
                for row in copied
            )
            + f"\nmanifest={manifest}\nspool={spool_path}"
        )
        diary = call_tool(
            "mempalace_diary_write",
            {
                "agent_name": "grok",
                "entry": entry,
                "topic": "grok_compact_archive",
                "wing": "",
            },
            timeout=12.0,
        )
    print(
        json.dumps(
            {
                "session_dir": str(session_dir),
                "copied": copied,
                "manifest": str(manifest),
                "journal": journal,
                "latest": latest,
                "spool": receipt,
                "diary": diary,
            },
            indent=2,
            default=str,
        )
    )
    return 0 if journal.get("status") in {"journal_appended", "journal_unchanged"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
