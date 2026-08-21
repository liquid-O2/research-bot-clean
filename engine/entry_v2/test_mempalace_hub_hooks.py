"""Regression checks for journal-first hub continuity (Grok/Claude/Codex)."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.entry_v2.mempalace_hub_client import HubCallError, call_tool, parse_tool_result
from engine.entry_v2.mempalace_lifecycle_hook import (
    normalize_payload,
    run_event,
    write_continuity_latest,
)
from engine.entry_v2.mempalace_transcript_tail import capture_transcript_tail


class ParseToolResultTests(unittest.TestCase):
    def test_diary_write_success_extracts_entry_id(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "success": True,
                                "entry_id": "diary_wing_grok_1",
                                "chunks": 1,
                            }
                        ),
                    }
                ]
            },
        }
        result = parse_tool_result(payload)
        self.assertTrue(result["success"])
        self.assertEqual(result["entry_id"], "diary_wing_grok_1")

    def test_search_returns_verbatim_drawer_text(self):
        marker = "GROK_MEMPALACE_ROUNDTRIP_FIXTURE"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "query": marker,
                                "results": [
                                    {
                                        "drawer_id": "diary_x",
                                        "text": marker,
                                        "similarity": 1.0,
                                    }
                                ],
                            }
                        ),
                    }
                ]
            },
        }
        result = parse_tool_result(payload)
        self.assertEqual(result["results"][0]["text"], marker)

    def test_rpc_error_is_not_success(self):
        result = parse_tool_result(
            {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "busy"}}
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "rpc_error")


class HubDownTests(unittest.TestCase):
    def test_call_tool_hub_down_returns_failed_dict_not_raise(self):
        def boom(*_args, **_kwargs):
            raise TimeoutError("hub hung")

        result = call_tool(
            "mempalace_diary_write",
            {"entry": "x"},
            transport=boom,
            timeout=0.1,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "hub_unavailable")
        self.assertEqual(result["error_type"], "TimeoutError")


class TranscriptTailTests(unittest.TestCase):
    def test_incremental_cursor_then_unchanged_then_growth(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            allowed = root / "sessions"
            allowed.mkdir()
            transcript = allowed / "chat.jsonl"
            transcript.write_bytes(b"aaaa\n")
            tail_dir = root / "tails"
            payload = {
                "session_id": "sess-1",
                "transcript_path": str(transcript),
            }
            env = {"MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed)}
            with patch.dict(os.environ, env, clear=False):
                first = capture_transcript_tail(payload, tail_dir=tail_dir)
                second = capture_transcript_tail(payload, tail_dir=tail_dir)
                transcript.write_bytes(b"aaaa\nbbbb\n")
                third = capture_transcript_tail(payload, tail_dir=tail_dir)
            self.assertEqual(first["status"], "tail_appended")
            self.assertEqual(first["bytes_copied"], 5)
            self.assertEqual(second["status"], "tail_unchanged")
            self.assertEqual(third["status"], "tail_appended")
            self.assertEqual(third["bytes_copied"], 5)
            self.assertEqual(Path(third["tail_path"]).read_bytes(), b"bbbb\n")
            self.assertEqual(stat.S_IMODE(Path(first["tail_path"]).stat().st_mode), 0o600)

    def test_shrunk_transcript_resets_cursor_instead_of_skipping(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            allowed = root / "sessions"
            allowed.mkdir()
            transcript = allowed / "chat.jsonl"
            transcript.write_bytes(b"0123456789")
            tail_dir = root / "tails"
            payload = {
                "session_id": "sess-2",
                "transcript_path": str(transcript),
            }
            env = {"MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed)}
            with patch.dict(os.environ, env, clear=False):
                capture_transcript_tail(payload, tail_dir=tail_dir)
                transcript.write_bytes(b"xyz")
                reset = capture_transcript_tail(payload, tail_dir=tail_dir)
            self.assertEqual(reset["status"], "tail_reset")
            self.assertEqual(reset["bytes_copied"], 3)
            self.assertEqual(Path(reset["tail_path"]).read_bytes(), b"xyz")

    def test_missing_transcript_is_explicit_not_a_hang(self):
        result = capture_transcript_tail({"session_id": "sess-3"})
        self.assertEqual(result["status"], "no-transcript")


class NormalizePayloadTests(unittest.TestCase):
    def test_grok_camel_case_and_codex_snake_case(self):
        grok = normalize_payload(
            {
                "hookEventName": "PreCompact",
                "sessionId": "abc",
                "transcriptPath": "/tmp/a.jsonl",
                "cwd": "/workspace",
            }
        )
        codex = normalize_payload(
            {
                "hook_event_name": "PreCompact",
                "session_id": "abc",
                "transcript_path": "/tmp/a.jsonl",
                "cwd": "/workspace",
            }
        )
        self.assertEqual(grok["session_id"], "abc")
        self.assertEqual(grok["hook_event_name"], "PreCompact")
        self.assertEqual(codex["transcript_path"], "/tmp/a.jsonl")
        self.assertEqual(grok["session_id"], codex["session_id"])

    def test_grok_snake_case_event_values_map_to_canonical(self):
        for raw in ("pre_compact", "preCompact", "PreCompact"):
            got = normalize_payload({"hookEventName": raw, "sessionId": "s"})
            self.assertEqual(got["hook_event_name"], "PreCompact", raw)
        prompt = normalize_payload({"hookEventName": "user_prompt_submit", "sessionId": "s"})
        self.assertEqual(prompt["hook_event_name"], "UserPromptSubmit")


class JournalFirstLifecycleTests(unittest.TestCase):
    def test_precompact_writes_journal_and_latest_file_when_hub_is_down(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            allowed = root / "codex"
            transcript = allowed / "sessions" / "rollout.jsonl"
            transcript.parent.mkdir(parents=True)
            transcript.write_text(
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "item_completed",
                            "item": {
                                "type": "UserMessage",
                                "id": "u1",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "MARKER-LOCAL-FIRST",
                                    }
                                ],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            journal = root / "journal.md"
            latest = root / "CONTINUITY_LATEST.md"
            spool = root / "spool"
            payload = {
                "hookEventName": "PreCompact",
                "sessionId": "lifecycle-1",
                "transcriptPath": str(transcript),
                "cwd": str(root),
                "trigger": "auto",
            }

            def dead_hub(*_a, **_k):
                raise TimeoutError("hub down")

            env = {
                "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed),
                "MEMPALACE_CONTINUITY_SPOOL_DIR": str(spool),
                "MEMPALACE_CONTINUITY_JOURNAL_PATH": str(journal),
                "MEMPALACE_CONTINUITY_LATEST_PATH": str(latest),
                "MEMPALACE_CONTINUITY_TAIL_DIR": str(root / "tails"),
            }
            with patch.dict(os.environ, env, clear=False):
                output, receipt = run_event(
                    payload,
                    hub_call=lambda *a, **k: call_tool(
                        "mempalace_diary_write", {"entry": "x"}, transport=dead_hub
                    ),
                )
            self.assertTrue(journal.is_file())
            self.assertIn("MARKER-LOCAL-FIRST", journal.read_text(encoding="utf-8"))
            self.assertTrue(latest.is_file())
            self.assertIn("MARKER-LOCAL-FIRST", latest.read_text(encoding="utf-8"))
            self.assertEqual(receipt["journal_status"], "journal_appended")
            self.assertFalse(receipt["palace_reconciled"])
            self.assertIn("journal_appended", output.get("systemMessage", ""))

    def test_continuity_latest_contains_verbatim_marker(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "CONTINUITY_LATEST.md"
            record = {
                "session_id": "s",
                "captured_at": "2026-08-20T19:00:00Z",
                "checkpoint": "GROK_MEMPALACE_ROUNDTRIP_X",
                "checkpoint_sha256": "a" * 64,
                "transcript_sha256": "b" * 64,
            }
            write_continuity_latest(record, path=path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("GROK_MEMPALACE_ROUNDTRIP_X", text)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


class GrokClaudeTranscriptTests(unittest.TestCase):
    def test_scan_grok_chat_history_extracts_user_query(self):
        from engine.entry_v2.mempalace_continuity_spool import scan_transcript

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            allowed = root / "sessions"
            allowed.mkdir()
            transcript = allowed / "chat_history.jsonl"
            transcript.write_text(
                json.dumps({"type": "system", "content": "you are grok"})
                + "\n"
                + json.dumps(
                    {
                        "type": "user",
                        "synthetic_reason": "compaction_meta",
                        "content": [{"type": "text", "text": "SUMMARY ONLY"}],
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "user",
                        "content": [{"type": "text", "text": "<user_query>\nkeep this\n</user_query>"}],
                    }
                )
                + "\n"
                + json.dumps({"type": "assistant", "content": "acknowledged keep this"})
                + "\n",
                encoding="utf-8",
            )
            env = {"MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed)}
            with patch.dict(os.environ, env, clear=False):
                scan = scan_transcript(transcript)
            texts = [m["text"] for m in scan["messages"]]
            self.assertTrue(any("keep this" in t for t in texts))
            self.assertFalse(any("SUMMARY ONLY" in t for t in texts))

    def test_markdown_segment_is_hashed_not_parsed(self):
        from engine.entry_v2.mempalace_continuity_spool import (
            scan_transcript,
            validate_transcript_path,
        )

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            allowed = root / "sessions"
            compact = allowed / "compaction"
            compact.mkdir(parents=True)
            segment = compact / "segment_000.md"
            segment.write_text("# HISTORICAL\nverbatim turn text\n", encoding="utf-8")
            env = {"MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed)}
            with patch.dict(os.environ, env, clear=False):
                validated = validate_transcript_path(str(segment))
                scan = scan_transcript(validated)
            self.assertEqual(scan["format"], "markdown_segment")
            self.assertEqual(scan["messages"], [])
            self.assertEqual(scan["transcript_bytes_hashed"], segment.stat().st_size)

    def test_capture_precompact_writes_file_pointers_for_grok(self):
        from engine.entry_v2.mempalace_continuity_spool import capture_precompact

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            allowed = root / "sessions" / "sess"
            compact = allowed / "compaction"
            compact.mkdir(parents=True)
            transcript = allowed / "chat_history.jsonl"
            transcript.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "content": [{"type": "text", "text": "<user_query>pointer-me</user_query>"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (compact / "INDEX.md").write_text("# Compaction Segment Index\n", encoding="utf-8")
            (compact / "segment_000.md").write_text("# HISTORICAL -- DO NOT EDIT\nfull turns\n", encoding="utf-8")
            spool = root / "spool"
            env = {
                "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(root / "sessions"),
                "MEMPALACE_CONTINUITY_SPOOL_DIR": str(spool),
            }
            payload = {
                "hook_event_name": "PreCompact",
                "session_id": "sess",
                "transcript_path": str(transcript),
                "cwd": str(root),
            }
            with patch.dict(os.environ, env, clear=False):
                record, _path, receipt = capture_precompact(payload)
            self.assertIn("Authoritative files", record["checkpoint"])
            self.assertIn("segment_000.md", record["checkpoint"])
            self.assertIn("pointer-me", record["checkpoint"])
            self.assertGreaterEqual(len(record["memory_files"]), 3)
            self.assertEqual(receipt["status"], "spooled")

    def test_user_prompt_submit_updates_latest_without_journal(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            allowed = root / "codex"
            transcript = allowed / "sessions" / "rollout.jsonl"
            transcript.parent.mkdir(parents=True)
            transcript.write_text(
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "item_completed",
                            "item": {
                                "type": "UserMessage",
                                "content": [{"type": "text", "text": "prompt-pointer"}],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            journal = root / "journal.md"
            journal.write_text("# Codex Continuity Journal\n\n", encoding="utf-8")
            latest = root / "CONTINUITY_LATEST.md"
            spool = root / "spool"
            payload = {
                "hookEventName": "user_prompt_submit",
                "sessionId": "prompt-1",
                "transcriptPath": str(transcript),
                "cwd": str(root),
            }
            env = {
                "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(allowed),
                "MEMPALACE_CONTINUITY_SPOOL_DIR": str(spool),
                "MEMPALACE_CONTINUITY_JOURNAL_PATH": str(journal),
                "MEMPALACE_CONTINUITY_LATEST_PATH": str(latest),
                "MEMPALACE_CONTINUITY_TAIL_DIR": str(root / "tails"),
            }
            before = journal.read_text(encoding="utf-8")
            with patch.dict(os.environ, env, clear=False):
                output, receipt = run_event(payload)
            self.assertEqual(receipt["status"], "prompt_pointer")
            self.assertTrue(latest.is_file())
            self.assertIn("prompt-pointer", latest.read_text(encoding="utf-8"))
            self.assertEqual(journal.read_text(encoding="utf-8"), before)
            self.assertTrue(output.get("suppressOutput"))


if __name__ == "__main__":
    unittest.main()
