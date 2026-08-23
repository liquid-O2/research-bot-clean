#!/usr/bin/env python3
"""Keep memory across sessions and compactions, without ever blocking one.

Output only, on every event, always (D-013 and D-108). A continuity hook that
refuses a compaction is the failure this whole system exists to undo: OptMem's
PreCompact returned `continue: false` while a compression was pending, and a
full session had no way forward.

PostCompact cannot inject context; it may only return `continue`. So everything
that has to survive a compaction rides on SessionStart with `source=compact`,
which does accept `additionalContext`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Mapping, Sequence, TextIO

ROOT = Path(os.environ.get("CLAUDE_METHOD_REPO_ROOT", "/workspace"))
LEDGER_TOOL = ROOT / "tools/memory_ledger.py"
SPOOL_ROOT = ROOT / "artifacts/cache/continuity"
START_HERE = ROOT / "START_HERE.md"
TAIL_LINES = 30
JsonObject = dict[str, object]


def load_ledger():
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


def session_start(payload: Mapping[str, object]) -> JsonObject:
    """Inject the memory tail at every session start, compaction included."""
    source = str(payload.get("source") or "startup")
    header = (f"Memory ledger, last {TAIL_LINES} entries "
              f"(session source: {source}). Add one with "
              "`python3 tools/memory_ledger.py note \"<line>\"`.")
    parts = [header, ledger_tail(), start_here_pointer()]
    return context("SessionStart", "\n\n".join(part for part in parts if part))


def spool_transcript(payload: Mapping[str, object]) -> Path | None:
    """Copy the verbatim transcript aside so a compaction loses nothing."""
    raw = payload.get("transcript_path")
    if not isinstance(raw, str) or not Path(raw).is_file():
        return None
    session = str(payload.get("session_id") or "unknown")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    SPOOL_ROOT.mkdir(parents=True, exist_ok=True)
    destination = SPOOL_ROOT / f"{session}-{stamp}.jsonl"
    shutil.copy2(raw, destination)
    return destination


def checkpoint_body(payload: Mapping[str, object], spool: Path | None) -> str:
    """Describe what this session was doing, in lines a later session can read."""
    rows = [
        f"- session: {payload.get('session_id')}",
        f"- trigger: {payload.get('trigger') or payload.get('source') or 'unknown'}",
        f"- cwd: {payload.get('cwd')}",
        f"- transcript spool: {spool if spool else 'not available'}",
        "- the method packet left context here; run the guard's engage command "
        "before the next repository write",
    ]
    return "\n".join(rows)


def pre_compact(payload: Mapping[str, object], stderr: TextIO) -> JsonObject:
    """Spool the transcript and write a checkpoint. Never refuse the compaction."""
    try:
        spool = spool_transcript(payload)
        ledger = load_ledger()
        ledger.append_checkpoint(checkpoint_body(payload, spool), ledger.ledger_path())
        return {"systemMessage": f"Continuity checkpoint written. Transcript spool: {spool}."}
    except (OSError, ValueError) as error:
        stderr.write(f"continuity checkpoint failed: {error}\n")
        return {"systemMessage": f"Continuity checkpoint failed: {error}. Compaction continues."}


def session_end(payload: Mapping[str, object], stderr: TextIO) -> JsonObject:
    """Close the session out in the ledger, quietly."""
    try:
        ledger = load_ledger()
        ledger.append_checkpoint(
            f"- session {payload.get('session_id')} ended "
            f"({payload.get('reason') or 'no reason given'})",
            ledger.ledger_path())
    except (OSError, ValueError) as error:
        stderr.write(f"session close-out failed: {error}\n")
    return {}


EVENTS = {"session-start": lambda p, e: session_start(p),
          "pre-compact": pre_compact,
          "session-end": session_end}


def main(argv: Sequence[str] | None = None, stdin: TextIO = sys.stdin,
         stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Run one continuity event and always allow the session to continue."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in EVENTS:
        raise ValueError(f"expected one of {sorted(EVENTS)}, got {arguments!r}")
    payload = json.load(stdin)
    try:
        response = EVENTS[arguments[0]](payload, stderr)
    except Exception as error:  # noqa: BLE001
        stderr.write(f"continuity hook failed: {type(error).__name__}: {error}\n")
        response = {}
    json.dump(response, stdout, ensure_ascii=False)
    stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
