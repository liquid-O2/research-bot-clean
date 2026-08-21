"""Unified PreCompact / SessionStart / Stop continuity hook.

Local journal and CONTINUITY_LATEST.md commit before any hub call.  Grok
ignores SessionStart stdout, so retrieve-after is the latest file plus MCP
search plus the project skill.  Codex/Claude still receive additionalContext
where the host honors it.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

try:
    from .mempalace_continuity_spool import (
        DEFAULT_HOOK_STATE_DIR,
        append_journal_checkpoint,
        append_receipt_log,
        capture_precompact,
        default_journal_path,
        discover_transcript_path,
        reconcile_path,
        _palace_entry,
    )
    from .mempalace_hub_client import call_tool
    from .mempalace_lossless_tape import (
        append_verbatim_users,
        clear_needs_recall,
        extract_user_queries,
        harvest_user_queries_from_session,
        is_nested_grok_session,
        needs_recall_record,
        recall_path,
        session_dir_from_transcript,
        set_needs_recall,
        snapshot_session,
        write_grok_memory_pointer,
        write_recall_index,
        append_ledger,
    )
    from .mempalace_transcript_tail import capture_transcript_tail
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mempalace_continuity_spool import (  # type: ignore
        DEFAULT_HOOK_STATE_DIR,
        append_journal_checkpoint,
        append_receipt_log,
        capture_precompact,
        default_journal_path,
        discover_transcript_path,
        reconcile_path,
        _palace_entry,
    )
    from mempalace_hub_client import call_tool  # type: ignore
    from mempalace_lossless_tape import (  # type: ignore
        append_verbatim_users,
        clear_needs_recall,
        extract_user_queries,
        harvest_user_queries_from_session,
        is_nested_grok_session,
        needs_recall_record,
        recall_path,
        session_dir_from_transcript,
        set_needs_recall,
        snapshot_session,
        write_grok_memory_pointer,
        write_recall_index,
        append_ledger,
    )
    from mempalace_transcript_tail import capture_transcript_tail  # type: ignore


HubCall = Callable[..., Mapping[str, Any]]
_HOOK_STDOUT_FD = os.dup(1)


def default_latest_path() -> Path:
    override = os.environ.get("MEMPALACE_CONTINUITY_LATEST_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return DEFAULT_HOOK_STATE_DIR / "CONTINUITY_LATEST.md"


def normalize_payload(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(raw or {})
    session_id = str(
        payload.get("session_id")
        or payload.get("sessionId")
        or os.environ.get("GROK_SESSION_ID")
        or ""
    )
    event = str(
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or os.environ.get("GROK_HOOK_EVENT")
        or ""
    )
    # Grok stdin uses camelCase keys and snake_case or camelCase values
    # (hookEventName=pre_compact, GROK_HOOK_EVENT=pre_compact).
    event_key = event.replace("-", "").replace("_", "").lower()
    event_map = {
        "precompact": "PreCompact",
        "postcompact": "PostCompact",
        "sessionstart": "SessionStart",
        "sessionend": "SessionEnd",
        "stop": "Stop",
        "userpromptsubmit": "UserPromptSubmit",
    }
    event = event_map.get(event_key, event)
    transcript = str(
        payload.get("transcript_path")
        or payload.get("transcriptPath")
        or ""
    )
    if not transcript:
        transcript = discover_transcript_path({**payload, "session_id": session_id})
    cwd = str(payload.get("cwd") or payload.get("workspaceRoot") or os.getcwd())
    trigger = str(payload.get("trigger") or payload.get("compactionTrigger") or "")
    source = str(payload.get("source") or payload.get("startSource") or "")
    reason = str(payload.get("reason") or "")
    stop_hook_active = payload.get("stopHookActive")
    if stop_hook_active is None:
        stop_hook_active = payload.get("stop_hook_active")
    if isinstance(stop_hook_active, str):
        stop_hook_active = stop_hook_active.lower() in {"1", "true", "yes"}
    else:
        stop_hook_active = bool(stop_hook_active)
    subagent_type = str(
        payload.get("subagentType") or payload.get("subagent_type") or ""
    )
    return {
        **payload,
        "session_id": session_id,
        "hook_event_name": event,
        "transcript_path": transcript,
        "cwd": cwd,
        "trigger": trigger,
        "source": source or ("compact" if event in {"PreCompact", "PostCompact"} else source),
        "reason": reason,
        "stop_hook_active": stop_hook_active,
        "subagent_type": subagent_type,
    }


def write_continuity_latest(
    record: Mapping[str, Any],
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or default_latest_path()
    if not target.is_absolute():
        raise ValueError("continuity latest path must be absolute")
    checkpoint = str(record.get("checkpoint") or "")
    files = record.get("memory_files")
    file_lines = ""
    if isinstance(files, list) and files:
        rows = []
        for item in files:
            if not isinstance(item, Mapping):
                continue
            rows.append(
                f"- `{item.get('path')}` sha256=`{item.get('sha256')}` "
                f"bytes=`{item.get('bytes')}`"
            )
        if rows:
            file_lines = (
                "\n## Authoritative files (this is the memory)\n\n"
                + "\n".join(rows)
                + "\n\nThe 6k checkpoint below is only last UI messages plus "
                "these pointers. After compact, read compaction/INDEX.md and "
                "every segment_*.md. Do not treat a compaction summary as the "
                "transcript.\n"
            )
    text = (
        "# MemPalace continuity latest\n\n"
        f"- captured_at: `{record.get('captured_at')}`\n"
        f"- session_id: `{record.get('session_id')}`\n"
        f"- checkpoint_sha256: `{record.get('checkpoint_sha256')}`\n"
        f"- transcript_sha256: `{record.get('transcript_sha256')}`\n"
        f"- transcript_path: `{record.get('transcript_path')}`\n"
        f"- journal: `{default_journal_path()}`\n"
        f"{file_lines}\n"
        "Treat the checkpoint below as a pointer plus last UI messages. "
        "Verify mutable repo state locally.\n\n"
        "```\n"
        f"{checkpoint}\n"
        "```\n"
    )
    encoded = text.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target.parent, 0o700)
    import tempfile

    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
        os.chmod(target, 0o600)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return {"status": "latest_written", "path": str(target), "bytes": len(encoded)}


def _emit(output: Mapping[str, Any]) -> None:
    payload = (json.dumps(dict(output), ensure_ascii=False) + "\n").encode("utf-8")
    os.write(_HOOK_STDOUT_FD, payload)


def _recall_context(payload: Mapping[str, Any]) -> str:
    parts = [
        "Lossless compaction tape: summaries are not the memory. "
        "Grok segment_*.md files truncate at 512KiB. Read RECALL.md, "
        "then every listed by_hash chat_history snapshot, then INDEX.md "
        "and each segment. Neural is dead. Tabular CatBoost. 2025H2 sealed."
    ]
    recall = recall_path()
    if recall.is_file():
        text = recall.read_text(encoding="utf-8", errors="replace")
        if len(text) > 16000:
            text = text[:16000] + "\n[TRUNCATED RECALL]\n"
        parts.append(text)
    latest = default_latest_path()
    if latest.is_file():
        text = latest.read_text(encoding="utf-8", errors="replace")
        if len(text) > 8000:
            text = text[:8000] + "\n[TRUNCATED CONTINUITY_LATEST]\n"
        parts.append(text)
    return "\n\n".join(parts)


def _snapshot_for_event(
    payload: Mapping[str, Any], event: str
) -> dict[str, Any] | None:
    session_dir = session_dir_from_transcript(str(payload.get("transcript_path") or ""))
    if session_dir is None:
        return None
    snapshot = snapshot_session(
        session_dir,
        event=event,
        session_id=str(payload.get("session_id") or session_dir.name),
    )
    write_recall_index(
        session_id=str(payload.get("session_id") or session_dir.name),
        session_dir=session_dir,
        snapshot=snapshot,
    )
    append_ledger(
        {
            "event": event,
            "session_id": payload.get("session_id"),
            "session_dir": str(session_dir),
            "files": snapshot.get("files"),
        }
    )
    try:
        harvest_user_queries_from_session(
            session_dir, session_id=str(payload.get("session_id") or "")
        )
    except OSError:
        pass
    try:
        write_grok_memory_pointer()
    except OSError:
        pass
    return snapshot


def run_event(
    payload: Mapping[str, Any],
    *,
    hub_call: HubCall | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = normalize_payload(payload)
    event = payload.get("hook_event_name") or ""
    receipt: dict[str, Any] = {
        "event": event,
        "session_id": payload.get("session_id"),
        "palace_reconciled": False,
        "journal_status": "skipped",
        "tail_status": "skipped",
    }

    nested = bool(payload.get("subagent_type")) or is_nested_grok_session(
        str(payload.get("session_id") or "")
    )
    receipt["nested_session"] = nested

    if event == "SessionStart":
        context = _recall_context(payload)
        output = {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": context,
            },
            "systemMessage": (
                "Lossless tape recall: read RECALL.md; compaction summaries are not the memory."
            ),
            "suppressOutput": False,
        }
        receipt["status"] = "recalled"
        return output, receipt

    if event == "PostCompact":
        snapshot = None
        if not nested:
            try:
                snapshot = _snapshot_for_event(payload, "PostCompact")
                set_needs_recall(str(payload.get("session_id") or ""))
                receipt["snapshot_files"] = len((snapshot or {}).get("files") or [])
            except Exception as exc:
                receipt["snapshot_error"] = type(exc).__name__
        context = _recall_context(payload)
        receipt["status"] = "postcompact_taped"
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": context,
            },
            "systemMessage": (
                "Lossless tape snapshotted after compact. Read "
                f"{recall_path()}. Summaries are not the memory."
            ),
            "suppressOutput": False,
        }, receipt

    if event == "Stop":
        reason = str(payload.get("reason") or "")
        active = bool(payload.get("stop_hook_active"))
        pending = needs_recall_record()
        if (
            pending
            and not nested
            and not active
            and reason in {"", "end_turn"}
        ):
            clear_needs_recall()
            recall = str(recall_path())
            message = (
                "COMPACTION TAPE: do not trust the compact summary. "
                f"Read {recall} first, then every listed by_hash chat_history "
                "snapshot, then compaction/INDEX.md and each segment_*.md. "
                "Segments truncate at 512KiB; by_hash snapshots and "
                "updates.jsonl tails are the complete tape. Then continue "
                "the user's last request."
            )
            receipt["status"] = "recall_blocked"
            return {
                "decision": "block",
                "reason": message,
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": message,
                },
                "suppressOutput": False,
            }, receipt
        if pending and active:
            clear_needs_recall()
        receipt["status"] = "stop_allowed"
        return {"suppressOutput": True}, receipt

    if event == "UserPromptSubmit":
        if not payload.get("transcript_path"):
            return {"suppressOutput": True}, {**receipt, "status": "prompt_no_transcript"}
        try:
            tail = capture_transcript_tail(payload)
            receipt["tail_status"] = str(tail.get("status"))
        except Exception as exc:
            receipt["tail_status"] = type(exc).__name__
        prompt_text = str(
            payload.get("prompt")
            or payload.get("userPrompt")
            or payload.get("text")
            or ""
        )
        queries = extract_user_queries(prompt_text)
        if not queries and prompt_text and len(prompt_text) <= 8000 and "<user_info>" not in prompt_text:
            queries = [prompt_text]
        if queries:
            try:
                append_verbatim_users(
                    queries,
                    session_id=str(payload.get("session_id") or ""),
                    source="UserPromptSubmit",
                )
            except OSError:
                pass
        if nested:
            receipt["status"] = "prompt_nested_skipped_latest"
            return {"suppressOutput": True}, receipt
        try:
            record, _spool_path, spool_receipt = capture_precompact(payload)
            receipt.update(spool_receipt)
            latest = write_continuity_latest(record)
            receipt["latest_status"] = latest.get("status")
            receipt["status"] = "prompt_pointer"
        except Exception as exc:
            receipt["status"] = "prompt_spool_failed"
            receipt["error_type"] = type(exc).__name__
        return {"suppressOutput": True}, receipt

    if event not in {"PreCompact", "SessionEnd"}:
        return {"suppressOutput": True}, {**receipt, "status": "ignored"}

    if nested and event == "SessionEnd":
        receipt["status"] = "sessionend_nested_skipped_latest"
        return {"suppressOutput": True}, receipt

    if event == "PreCompact" and not nested:
        try:
            snapshot = _snapshot_for_event(payload, "PreCompact")
            receipt["snapshot_files"] = len((snapshot or {}).get("files") or [])
        except Exception as exc:
            receipt["snapshot_error"] = type(exc).__name__

    try:
        tail = capture_transcript_tail(payload)
    except Exception as exc:
        tail = {"status": "tail_failed", "error_type": type(exc).__name__}
    receipt["tail_status"] = str(tail.get("status"))
    if isinstance(tail.get("tail_path"), str):
        receipt["tail_path"] = tail["tail_path"]

    try:
        record, spool_path, spool_receipt = capture_precompact(payload)
    except Exception as exc:
        receipt.update(
            status="spool_failed",
            error_type=type(exc).__name__,
        )
        return {
            "systemMessage": (
                "MemPalace continuity spool failed. Local tail/journal may still "
                "exist; do not rely on palace recall until the next successful checkpoint."
            ),
            "suppressOutput": False,
        }, receipt
    receipt.update(spool_receipt)

    try:
        journal = append_journal_checkpoint(record)
    except Exception as exc:
        journal = {"status": "journal_failed", "error_type": type(exc).__name__}
    receipt["journal_status"] = journal.get("status")
    for key in ("journal_path", "journal_sha256", "journal_entry_sha256"):
        value = journal.get(key)
        if isinstance(value, str):
            receipt[key] = value

    try:
        latest = write_continuity_latest(record)
        receipt["latest_status"] = latest.get("status")
        receipt["latest_path"] = latest.get("path")
    except Exception as exc:
        receipt["latest_status"] = "latest_failed"
        receipt["latest_error_type"] = type(exc).__name__

    def writer(item: Mapping[str, Any]) -> Mapping[str, Any]:
        arguments = {
            "agent_name": "grok",
            "entry": _palace_entry(item),
            "topic": "precompact_continuity",
            "wing": "",
        }
        if hub_call is not None:
            return dict(hub_call("mempalace_diary_write", arguments))
        return call_tool("mempalace_diary_write", arguments, timeout=6.0)

    reconciliation = reconcile_path(spool_path, writer=writer)
    receipt["reconcile"] = [reconciliation.get("status")]
    receipt["palace_reconciled"] = reconciliation.get("status") in {
        "reconciled",
        "already_reconciled",
    }
    checkpoint_sha = str(receipt.get("checkpoint_sha256") or "")[:12]
    palace_state = "hub-reconciled" if receipt["palace_reconciled"] else "spooled"
    journal_state = str(receipt.get("journal_status") or "journal-unknown")
    system = (
        "MemPalace PreCompact checkpoint captured "
        f"({journal_state}, {palace_state}, sha256={checkpoint_sha})."
    )
    output: dict[str, Any] = {
        "systemMessage": system,
        "suppressOutput": False,
    }
    return output, receipt


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        payload = {}
    if not isinstance(payload, Mapping):
        payload = {}
    output, receipt = run_event(payload)
    append_receipt_log(str(receipt.get("event") or "LIFECYCLE"), receipt)
    _emit(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
