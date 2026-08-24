#!/usr/bin/env python3
"""Keep memory and transcript history without blocking lifecycle events.

Output only, on every event, always (D-013 and D-108). The old OptMem
PreCompact hook returned ``continue: false`` while compression was pending.
That deadlocked a full session, so continuity hooks report failures and never
deny compaction or session shutdown.

PostCompact cannot inject context. SessionStart with ``source=compact`` owns
restoration because that event accepts ``additionalContext``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Mapping, Sequence, TextIO

from transcript_archive import (
    archive_transcript,
    defer_transcript,
    reconcile_pending_transcripts,
)

ROOT = Path(os.environ.get("CODEX_METHOD_REPO_ROOT")
            or os.environ.get("CLAUDE_METHOD_REPO_ROOT")
            or Path(__file__).resolve().parents[2])
LEDGER_TOOL = ROOT / "tools/memory_ledger.py"
START_HERE = ROOT / "START_HERE.md"
TAIL_LINES = 30
JsonObject = dict[str, object]
__all__ = ("main",)


def load_ledger() -> ModuleType:
    """Import the ledger tool so hooks and the CLI share one implementation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("hook_memory_ledger", LEDGER_TOOL)
    if spec is None or spec.loader is None:
        raise ValueError(f"memory ledger tool is missing at {LEDGER_TOOL}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hook_memory_ledger"] = module
    spec.loader.exec_module(module)
    return module


def context(event: str, text: str) -> JsonObject:
    """Return additional context for an event that accepts it."""
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def ledger_tail(count: int = TAIL_LINES) -> str:
    """Return the most recent memories, or a readable reason there are none."""
    ledger = load_ledger()
    entries = ledger.tail(count, ledger.ledger_path())
    return "\n".join(entries) if entries else "The memory ledger is empty."


def start_here_pointer() -> str:
    """Point at the cold-start document without inlining it."""
    if not START_HERE.is_file():
        return ""
    return f"Read {START_HERE} for the project, the goal, and what has already failed."


def reconcile_children(stderr: TextIO) -> None:
    """Finish child archives without changing the lifecycle event outcome."""
    try:
        reconcile_pending_transcripts()
    except Exception as error:  # noqa: BLE001
        stderr.write(f"child transcript reconciliation failed: {type(error).__name__}: {error}\n")


def session_start(payload: Mapping[str, object], stderr: TextIO) -> JsonObject:
    """Inject the memory tail at every session start, compaction included."""
    reconcile_children(stderr)
    source = str(payload.get("source") or "startup")
    header = (f"Memory ledger, last {TAIL_LINES} entries "
              f"(session source: {source}). Add one with "
              "`python3 tools/memory_ledger.py note \"<line>\"`.")
    parts = [header, ledger_tail(), start_here_pointer()]
    return context("SessionStart", "\n\n".join(part for part in parts if part))


def checkpoint_body(payload: Mapping[str, object], archive: Path) -> str:
    """Describe what this session was doing, in lines a later session can read."""
    rows = [
        f"- session: {payload.get('session_id')}",
        f"- trigger: {payload.get('trigger') or payload.get('source') or 'unknown'}",
        f"- cwd: {payload.get('cwd')}",
        f"- transcript archive: {archive}",
        "- SessionStart restores the exact method packet before compact continuation",
    ]
    return "\n".join(rows)


def pre_compact(payload: Mapping[str, object], _stderr: TextIO) -> JsonObject:
    """Archive the transcript and checkpoint its object without blocking."""
    reconcile_children(_stderr)
    archived = archive_transcript(payload.get("transcript_path"))
    ledger = load_ledger()
    ledger.append_checkpoint(checkpoint_body(payload, archived), ledger.ledger_path())
    return {}


def session_end(payload: Mapping[str, object], _stderr: TextIO) -> JsonObject:
    """Archive the final transcript without adding a generic checkpoint."""
    reconcile_children(_stderr)
    archive_transcript(payload.get("transcript_path"))
    return {}


def subagent_stop(payload: Mapping[str, object], _stderr: TextIO) -> JsonObject:
    defer_transcript(payload.get("agent_transcript_path"), payload.get("turn_id"))
    return {}


EVENTS = {"session-start": session_start,
          "pre-compact": pre_compact,
          "session-end": session_end,
          "subagent-stop": subagent_stop}


def main(argv: Sequence[str] | None = None, stdin: TextIO = sys.stdin,
         stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Run one event and return 0. Example: ``main([event], stdin, stdout)``."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in EVENTS:
        raise ValueError(f"expected one of {sorted(EVENTS)}, got {arguments!r}")
    try:
        payload = json.load(stdin)
        response = EVENTS[arguments[0]](payload, stderr)
    except Exception as error:  # noqa: BLE001
        stderr.write(f"continuity hook failed: {type(error).__name__}: {error}\n")
        response = {}
    json.dump(response, stdout, ensure_ascii=False)
    stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
