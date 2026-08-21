from __future__ import annotations

import json
import hashlib
import os
import stat
from pathlib import Path
from unittest.mock import patch

import jsonschema

from engine.entry_v2.mempalace_continuity_spool import capture_precompact
from engine.entry_v2.mempalace_continuity_spool import append_journal_checkpoint
from engine.entry_v2.mempalace_continuity_spool import load_for_session_start
from engine.entry_v2.mempalace_continuity_spool import reconcile_path
from engine.entry_v2.mempalace_continuity_spool import render_for_model
from engine.entry_v2.mempalace_recall_hook import build_context
from engine.entry_v2.mempalace_recall_hook import recall_for_payload


# Copied from Codex CLI 0.147.0's generated
# session-start.command.output.schema.json. Keeping the narrow protocol schema
# beside the hook test avoids depending on a temporary source checkout.
SESSION_START_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "continue": {"type": "boolean", "default": True},
        "stopReason": {"type": "string", "default": None},
        "suppressOutput": {"type": "boolean", "default": False},
        "systemMessage": {"type": "string", "default": None},
        "hookSpecificOutput": {
            "default": None,
            "allOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "hookEventName": {"type": "string", "const": "SessionStart"},
                        "additionalContext": {"type": "string", "default": None},
                    },
                    "required": ["hookEventName"],
                }
            ],
        },
    },
}


def _reader_with(entries):
    def reader(**kwargs):
        assert kwargs == {"agent_name": "codex", "last_n": 5, "wing": ""}
        return {"agent": "codex", "entries": entries}

    return reader


def test_compact_recall_is_verbatim_bounded_and_schema_valid():
    marker = "ENTRYV2-MEMPALACE-ROUNDTRIP-20260816T-current-D096"
    entries = [
        {
            "timestamp": "2026-08-16T09:53:19Z",
            "topic": "entry_v2_continuity",
            "content": f"verbatim:{marker}",
        },
        {
            "timestamp": "2026-08-16T09:24:53Z",
            "topic": "entry_v2",
            "content": "older exact milestone",
        },
    ]
    output, receipt = recall_for_payload(
        {"source": "compact", "session_id": "thread-1"},
        _reader_with(entries),
        max_chars=700,
    )

    context = output["hookSpecificOutput"]["additionalContext"]
    assert marker in context
    assert "older exact milestone" in context
    assert len(context) <= 700
    assert receipt["status"] == "recalled"
    assert receipt["entries"] == 2

    jsonschema.validate(output, SESSION_START_OUTPUT_SCHEMA)


def test_startup_and_resume_recall_but_clear_does_not():
    entries = [{"timestamp": "t", "topic": "x", "content": "saved"}]
    resume, _ = recall_for_payload({"source": "resume"}, _reader_with(entries))
    startup, startup_receipt = recall_for_payload(
        {"source": "startup"}, _reader_with(entries)
    )
    clear, clear_receipt = recall_for_payload(
        {"source": "clear"},
        lambda **_: (_ for _ in ()).throw(AssertionError("must not read")),
    )

    assert resume["hookSpecificOutput"]["additionalContext"].endswith(
        "</mempalace-recall>"
    )
    assert "saved" in startup["hookSpecificOutput"]["additionalContext"]
    assert startup_receipt["status"] == "recalled"
    assert clear == {}
    assert clear_receipt["status"] == "skipped"


def test_failure_injects_explicit_recovery_not_exception_text():
    def broken_reader(**_):
        raise RuntimeError("secret exception detail")

    output, receipt = recall_for_payload({"source": "compact"}, broken_reader)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "mempalace_diary_read" in context
    assert "Do not guess" in context
    assert "secret exception detail" not in context
    assert receipt["status"] == "error"


def test_oversize_newest_entry_uses_exact_prefix_with_marker():
    content = "0123456789" * 200
    context, used = build_context(
        [{"timestamp": "t", "topic": "big", "content": content}],
        max_chars=512,
    )
    assert used == 1
    assert content[:80] in context
    assert "TRUNCATED BY BOUNDED MEMORIES HOOK" in context
    assert len(context) <= 512


def _completed(item_type: str, text: str, *, phase: str = "") -> dict:
    item = {
        "type": item_type,
        "id": f"id-{item_type}",
        "content": [{"type": "text" if item_type == "UserMessage" else "Text", "text": text}],
    }
    if phase:
        item["phase"] = phase
    return {
        "type": "event_msg",
        "payload": {"type": "item_completed", "item": item},
    }


def _fixture_spool(tmp_path: Path):
    allowed = tmp_path / "codex"
    transcript = allowed / "sessions" / "rollout.jsonl"
    transcript.parent.mkdir(parents=True)
    secret = "sk-THIS_MUST_NEVER_REACH_THE_SPOOL_123456"
    lines = [
        _completed("UserMessage", "old window content"),
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "item": {"type": "ContextCompaction", "id": "compact-1"},
            },
        },
        _completed(
            "UserMessage",
            f"SAFE-CHECKPOINT-D096\napi_key = {secret}\nAuthorization: Bearer bearer-secret",
        ),
        {
            "type": "response_item",
            "payload": {"type": "custom_tool_call_output", "output": f"tool-secret-{secret}"},
        },
        _completed("AgentMessage", "durable assistant decision", phase="commentary"),
    ]
    transcript.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    (tmp_path / "index.md").write_text("project state pointer", encoding="utf-8")
    spool_dir = tmp_path / "spool"
    payload = {
        "cwd": str(tmp_path),
        "hook_event_name": "PreCompact",
        "model": "gpt-5.6",
        "session_id": "session-test",
        "transcript_path": str(transcript),
        "trigger": "auto",
        "turn_id": "turn-test",
    }
    with patch.dict(
        os.environ,
        {
            "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed),
            "MEMPALACE_CONTINUITY_SPOOL_DIR": str(spool_dir),
        },
    ):
        record, path, receipt = capture_precompact(
            payload, captured_at="2026-08-16T10:00:00Z"
        )
    return payload, record, path, receipt, secret, transcript, allowed, spool_dir


def test_precompact_spool_is_atomic_bounded_redacted_and_verifiable(tmp_path=None):
    if tmp_path is None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            return test_precompact_spool_is_atomic_bounded_redacted_and_verifiable(Path(directory))
    payload, record, path, receipt, secret, transcript, _, _ = _fixture_spool(tmp_path)

    checkpoint = record["checkpoint"]
    assert "SAFE-CHECKPOINT-D096" in checkpoint
    assert "durable assistant decision" in checkpoint
    assert "old window content" not in checkpoint
    assert "tool-secret" not in checkpoint
    assert secret not in path.read_text(encoding="utf-8")
    assert "bearer-secret" not in path.read_text(encoding="utf-8")
    assert "[REDACTED" in checkpoint
    assert len(checkpoint) <= 6_000
    assert receipt["status"] == "spooled"
    assert record["transcript_sha256"] == hashlib.sha256(transcript.read_bytes()).hexdigest()
    assert record["source"]["trigger"] == "auto"
    assert record["session_id"] == payload["session_id"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not list(path.parent.glob(f".{path.name}.*"))
    assert record["project"]["state_files"][0]["path"] == str(tmp_path / "index.md")


def test_journal_checkpoint_is_append_only_atomic_and_idempotent(tmp_path=None):
    if tmp_path is None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            return test_journal_checkpoint_is_append_only_atomic_and_idempotent(
                Path(directory)
            )
    _, record, _, _, secret, _, _, _ = _fixture_spool(tmp_path)
    journal = tmp_path / "journal.md"
    journal.write_text("# Manual journal\n\nkeep this note\n", encoding="utf-8")

    first = append_journal_checkpoint(record, journal_path=journal)
    second = append_journal_checkpoint(record, journal_path=journal)
    rendered = journal.read_text(encoding="utf-8")

    assert first["status"] == "journal_appended"
    assert second["status"] == "journal_unchanged"
    assert rendered.startswith("# Manual journal\n\nkeep this note\n")
    assert rendered.count(record["checkpoint_sha256"]) == 2
    assert "SAFE-CHECKPOINT-D096" in rendered
    assert secret not in rendered
    assert stat.S_IMODE(journal.stat().st_mode) == 0o600
    assert not list(journal.parent.glob(f".{journal.name}.*.tmp"))


def test_sessionstart_reads_exact_spool_first_and_keeps_palace_distinct(tmp_path=None):
    if tmp_path is None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            return test_sessionstart_reads_exact_spool_first_and_keeps_palace_distinct(
                Path(directory)
            )
    payload, _, _, _, _, _, allowed, spool_dir = _fixture_spool(tmp_path)
    session_payload = {
        "source": "compact",
        "session_id": payload["session_id"],
        "transcript_path": payload["transcript_path"],
    }

    def loader(value):
        with patch.dict(
            os.environ,
            {
                "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed),
                "MEMPALACE_CONTINUITY_SPOOL_DIR": str(spool_dir),
            },
        ):
            return load_for_session_start(value)

    output, receipt = recall_for_payload(
        session_payload,
        _reader_with(
            [{"timestamp": "t", "topic": "palace", "content": "PALACE-MILESTONE"}]
        ),
        spool_loader=loader,
        spool_renderer=render_for_model,
    )
    context = output["hookSpecificOutput"]["additionalContext"]
    assert context.index("<mempalace-continuity-spool>") < context.index(
        "<mempalace-recall"
    )
    assert "SAFE-CHECKPOINT-D096" in context
    assert "PALACE-MILESTONE" in context
    assert "spool-only (pending palace reconciliation)" in context
    assert receipt["status"] == "recalled_with_spool"
    assert receipt["spool_status"] == "loaded"
    assert receipt["palace_status"] == "recalled"
    assert len(context) <= 11_000


def test_reconciled_multichunk_spool_is_not_reinjected(tmp_path=None):
    if tmp_path is None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            return test_reconciled_multichunk_spool_is_not_reinjected(Path(directory))
    payload, record, path, _, _, _, allowed, spool_dir = _fixture_spool(tmp_path)
    record.update(
        palace_reconciled=True,
        palace_reconciled_at="2026-08-16T10:01:00Z",
        palace_entry_id="diary-1",
        palace_transport="test",
    )
    path.write_text(json.dumps(record), encoding="utf-8")
    timestamp = "2026-08-16T10:01:00Z"
    entries = [
        {
            "timestamp": timestamp,
            "topic": "precompact_continuity",
            "content": f"CODEX_PRECOMPACT_CONTINUITY_V1\nspool_id:{record['checkpoint_sha256']}\nchunk-1",
        },
        {
            "timestamp": timestamp,
            "topic": "precompact_continuity",
            "content": "chunk-2-without-marker",
        },
        {
            "timestamp": "2026-08-16T10:02:00Z",
            "topic": "entry_v2_continuity",
            "content": "DISTINCT-MILESTONE",
        },
    ]
    session_payload = {
        "source": "resume",
        "session_id": payload["session_id"],
        "transcript_path": payload["transcript_path"],
    }

    def loader(value):
        with patch.dict(
            os.environ,
            {
                "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed),
                "MEMPALACE_CONTINUITY_SPOOL_DIR": str(spool_dir),
            },
        ):
            return load_for_session_start(value)

    output, _ = recall_for_payload(
        session_payload,
        _reader_with(entries),
        spool_loader=loader,
        spool_renderer=render_for_model,
    )
    context = output["hookSpecificOutput"]["additionalContext"]
    assert context.count("SAFE-CHECKPOINT-D096") == 1
    assert "chunk-1" not in context
    assert "chunk-2-without-marker" not in context
    assert "DISTINCT-MILESTONE" in context


def test_corrupt_spool_checksum_is_not_injected(tmp_path=None):
    if tmp_path is None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            return test_corrupt_spool_checksum_is_not_injected(Path(directory))
    payload, record, path, _, _, _, allowed, spool_dir = _fixture_spool(tmp_path)
    record["checkpoint"] = "tampered"
    path.write_text(json.dumps(record), encoding="utf-8")
    session_payload = {
        "source": "compact",
        "session_id": payload["session_id"],
        "transcript_path": payload["transcript_path"],
    }
    with patch.dict(
        os.environ,
        {
            "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed),
            "MEMPALACE_CONTINUITY_SPOOL_DIR": str(spool_dir),
        },
    ):
        loaded, receipt = load_for_session_start(session_payload)
    assert loaded is None
    assert receipt["status"] == "not_found"


def test_reconcile_marks_palace_provenance_only_after_confirmed_write(tmp_path=None):
    if tmp_path is None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            return test_reconcile_marks_palace_provenance_only_after_confirmed_write(
                Path(directory)
            )
    _, _, path, _, _, _, _, _ = _fixture_spool(tmp_path)

    failed = reconcile_path(
        path, writer=lambda _: {"success": False, "status": "writer_lease_busy"}
    )
    assert failed["status"] == "writer_lease_busy"
    assert json.loads(path.read_text())["palace_reconciled"] is False

    success = reconcile_path(
        path,
        writer=lambda _: {
            "success": True,
            "status": "reconciled",
            "transport": "test_writer",
            "entry_id": "entry-1",
        },
    )
    assert success["status"] == "reconciled"
    updated = json.loads(path.read_text())
    assert updated["palace_reconciled"] is True
    assert updated["palace_entry_id"] == "entry-1"
    assert "storage: palace+spool" in render_for_model(updated)
