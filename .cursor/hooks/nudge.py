#!/usr/bin/env python3
"""Cursor lifecycle hook. Memory persist on compact. Retrieve after compact and on session start. Thin reminders. Does not block."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/workspace")
LEDGER = ROOT / "tools" / "memory_ledger.py"
STATE_DIR = ROOT / ".cursor" / "hooks" / "state"
PENDING = STATE_DIR / "pending-retrieve"
WAKE_FP = STATE_DIR / "wake-fingerprint"
NOTE_ASKED = STATE_DIR / "note-asked"

START_NUDGE = (
    "pstack-lab. /poteto-mode. poteto-agent. "
    "Read the principles index. Matching triggers are equal. "
    "You write MEMORY.md notes. The human does not. "
    "Every reply to the user follows unslop."
)
TURN_NUDGE = (
    "Stay on /poteto-mode. Matching principle triggers are equal. "
    "Sweep defects, repair once, prove once. Unslop the reply."
)
NOTE_FOLLOWUP = (
    "This session has no new MEMORY.md note. "
    "If a lasting fact exists, run "
    "python3 tools/memory_ledger.py note \"<one line>\". "
    "One fact, under 280 bytes, unslopped. "
    "If nothing lasting happened, reply NONE and stop."
)


def event_name(payload: dict) -> str:
    for key in ("hook_event_name", "hookEventName", "event"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.write("\n")


def run_ledger(args: list[str]) -> str:
    proc = subprocess.run(
        ["python3", str(LEDGER), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


WAKE_COUNT = 12


def lasting_notes(raw: str) -> list[str]:
    lines = [line for line in raw.splitlines() if line.startswith("- ")]
    kept = [line for line in lines if " COMPACT session " not in line]
    return kept[-WAKE_COUNT:]


def memory_block() -> str:
    tail = run_ledger(["tail", "40"])
    notes = lasting_notes(tail)
    if not notes:
        return "MEMORY.md wake empty. Run python3 tools/memory_ledger.py recall yourself."
    return "MEMORY.md wake:\n" + "\n".join(notes)


def wake_fingerprint() -> str:
    return "\n".join(lasting_notes(run_ledger(["tail", "40"])))


def reset_session_state() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    WAKE_FP.write_text(wake_fingerprint(), encoding="utf-8")
    NOTE_ASKED.unlink(missing_ok=True)


def on_session_start() -> dict:
    reset_session_state()
    return {"additional_context": START_NUDGE + "\n\n" + memory_block()}


def on_turn(payload: dict) -> dict:
    if PENDING.is_file():
        PENDING.unlink(missing_ok=True)
        return {
            "additional_context": (
                "Context just compacted. Re-ground from MEMORY.md.\n\n"
                + memory_block()
            )
        }
    # Cloud agents skip sessionStart. First prompt still needs the tail.
    if payload.get("is_background_agent") is True:
        if not WAKE_FP.is_file():
            reset_session_state()
        return {"additional_context": START_NUDGE + "\n\n" + memory_block()}
    return {"additional_context": TURN_NUDGE}


def on_precompact(payload: dict) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PENDING.write_text("1\n", encoding="utf-8")
    trigger = payload.get("trigger") or "unknown"
    usage = payload.get("context_usage_percent")
    messages = payload.get("message_count")
    first = payload.get("is_first_compaction")
    session = payload.get("session_id") or "cursor"
    record = f"compact-{trigger}-{usage}"
    body = (
        f"- session: {session}\n"
        f"- transcript record: {record}\n"
        f"- trigger: {trigger}\n"
        f"- context_usage_percent: {usage}\n"
        f"- message_count: {messages}\n"
        f"- is_first_compaction: {first}\n"
    )
    run_ledger(["checkpoint", body])
    return {
        "user_message": (
            "Compaction started. A MEMORY.md checkpoint was written. "
            "The next prompt will re-inject the ledger tail."
        )
    }


def on_stop(payload: dict) -> dict:
    if payload.get("status") and payload.get("status") != "completed":
        return {}
    try:
        loop_count = int(payload.get("loop_count") or 0)
    except (TypeError, ValueError):
        loop_count = 0
    if loop_count >= 1 or NOTE_ASKED.is_file():
        return {}
    current = wake_fingerprint()
    prior = WAKE_FP.read_text(encoding="utf-8") if WAKE_FP.is_file() else ""
    if current != prior:
        return {}
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_ASKED.write_text("1\n", encoding="utf-8")
    return {"followup_message": NOTE_FOLLOWUP}


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    event = event_name(payload).lower().replace("_", "")
    if event in {"sessionstart"}:
        emit(on_session_start())
        return
    if event in {"precompact"}:
        emit(on_precompact(payload))
        return
    if event in {"stop"}:
        emit(on_stop(payload))
        return
    emit(on_turn(payload))


if __name__ == "__main__":
    main()
