"""Lossless compaction tape: never overwrite unique bytes; recall after compact."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.entry_v2.mempalace_lifecycle_hook import run_event
from engine.entry_v2.mempalace_lossless_tape import (
    append_verbatim_users,
    conversation_tape_path,
    extract_user_queries,
    harvest_conversation_from_jsonl,
    is_nested_grok_session,
    needs_recall_record,
    set_needs_recall,
    snapshot_session,
    store_by_hash,
    write_recall_index,
)


class StoreByHashTests(unittest.TestCase):
    def test_same_hash_is_noop_different_hash_keeps_both(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            dest = root / "dest"
            first = root / "chat_history.jsonl"
            first.write_text("turn-one\n", encoding="utf-8")
            a = store_by_hash(first, dest)
            self.assertEqual(a["status"], "copied")
            b = store_by_hash(first, dest)
            self.assertEqual(b["status"], "exists")
            self.assertEqual(a["archive"], b["archive"])
            first.write_text("turn-two-after-compact\n", encoding="utf-8")
            c = store_by_hash(first, dest)
            self.assertEqual(c["status"], "copied")
            self.assertNotEqual(a["sha256"], c["sha256"])
            self.assertTrue(Path(a["archive"]).is_file())
            self.assertTrue(Path(c["archive"]).is_file())
            self.assertEqual(Path(a["archive"]).read_text(encoding="utf-8"), "turn-one\n")
            self.assertEqual(
                Path(c["archive"]).read_text(encoding="utf-8"), "turn-two-after-compact\n"
            )


class NestedSessionTests(unittest.TestCase):
    def test_child_under_subagents_is_nested(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            group = root / "%2Fworkspace"
            parent = group / "parent-sess"
            child_id = "child-sess"
            (parent / "subagents" / child_id).mkdir(parents=True)
            (group / child_id).mkdir()
            env = {"MEMPALACE_GROK_SESSIONS_ROOT": str(root)}
            with patch.dict(os.environ, env, clear=False):
                self.assertTrue(is_nested_grok_session(child_id))
                self.assertFalse(is_nested_grok_session("parent-sess"))


class SnapshotAndRecallTests(unittest.TestCase):
    def test_snapshot_lists_chat_history_and_truncated_segment(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            session = root / "sess"
            compact = session / "compaction"
            compact.mkdir(parents=True)
            (session / "chat_history.jsonl").write_text(
                '{"type":"user","content":[{"type":"text","text":"<user_query>keep me</user_query>"}]}\n',
                encoding="utf-8",
            )
            (compact / "INDEX.md").write_text("# Compaction Segment Index\n", encoding="utf-8")
            segment = compact / "segment_000.md"
            segment.write_bytes(b"x" * 524288 + b"\n[... TRUNCATED at 524288 bytes, 9 turns omitted ...]\n")
            env = {
                "MEMPALACE_SOURCES_ROOT": str(root / "sources"),
                "MEMPALACE_HOOK_STATE_DIR": str(root / "hook_state"),
            }
            with patch.dict(os.environ, env, clear=False):
                snap = snapshot_session(session, event="PreCompact", session_id="sess")
                statuses = {row["status"] for row in snap["files"]}
                self.assertIn("copied", statuses)
                truncated = [row for row in snap["files"] if row.get("truncated_segment")]
                self.assertTrue(truncated)
                recall = write_recall_index(
                    session_id="sess", session_dir=session, snapshot=snap
                )
                text = recall.read_text(encoding="utf-8")
                self.assertIn("summaries are not the memory", text.lower())
                self.assertIn("TRUNCATED", text)
                self.assertIn("keep me", extract_user_queries(
                    (session / "chat_history.jsonl").read_text(encoding="utf-8")
                )[0])


class HookIntegrationTests(unittest.TestCase):
    def test_nested_prompt_does_not_overwrite_parent_latest(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            group = root / "sessions" / "%2Fworkspace"
            parent = group / "parent-sess"
            child = group / "child-sess"
            (parent / "subagents" / "child-sess").mkdir(parents=True)
            child.mkdir(parents=True)
            transcript = child / "chat_history.jsonl"
            transcript.write_text("{}\n", encoding="utf-8")
            latest = root / "CONTINUITY_LATEST.md"
            latest.write_text("PARENT POINTER\n", encoding="utf-8")
            env = {
                "MEMPALACE_GROK_SESSIONS_ROOT": str(root / "sessions"),
                "MEMPALACE_CONTINUITY_LATEST_PATH": str(latest),
                "MEMPALACE_HOOK_STATE_DIR": str(root / "hook_state"),
                "MEMPALACE_CONTINUITY_SPOOL_DIR": str(root / "spool"),
                "MEMPALACE_CONTINUITY_TAIL_DIR": str(root / "tails"),
                "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(root / "sessions"),
            }
            payload = {
                "hookEventName": "user_prompt_submit",
                "sessionId": "child-sess",
                "transcriptPath": str(transcript),
                "cwd": str(root),
            }
            with patch.dict(os.environ, env, clear=False):
                _output, receipt = run_event(payload)
            self.assertTrue(receipt.get("nested_session"))
            self.assertEqual(receipt["status"], "prompt_nested_skipped_latest")
            self.assertEqual(latest.read_text(encoding="utf-8"), "PARENT POINTER\n")

    def test_stop_blocks_once_when_needs_recall(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            env = {"MEMPALACE_HOOK_STATE_DIR": str(root / "hook_state")}
            with patch.dict(os.environ, env, clear=False):
                set_needs_recall("sess")
                output, receipt = run_event(
                    {
                        "hookEventName": "Stop",
                        "sessionId": "sess",
                        "reason": "end_turn",
                        "cwd": str(root),
                    }
                )
                self.assertEqual(receipt["status"], "recall_blocked")
                self.assertEqual(output.get("decision"), "block")
                self.assertIn("RECALL.md", output.get("reason", ""))
                self.assertIsNone(needs_recall_record())
                output2, receipt2 = run_event(
                    {
                        "hookEventName": "Stop",
                        "sessionId": "sess",
                        "reason": "end_turn",
                        "cwd": str(root),
                    }
                )
                self.assertEqual(receipt2["status"], "stop_allowed")
                self.assertNotEqual(output2.get("decision"), "block")

    def test_postcompact_snapshots_and_sets_needs_recall(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            session = root / "allowed" / "sess"
            compact = session / "compaction"
            compact.mkdir(parents=True)
            (session / "chat_history.jsonl").write_text("post-compact-chat\n", encoding="utf-8")
            (compact / "INDEX.md").write_text("# idx\n", encoding="utf-8")
            (compact / "segment_000.md").write_text("# HISTORICAL\nfull turn\n", encoding="utf-8")
            env = {
                "MEMPALACE_SOURCES_ROOT": str(root / "sources"),
                "MEMPALACE_HOOK_STATE_DIR": str(root / "hook_state"),
                "MEMPALACE_GROK_MEMORY_PATH": str(root / "MEMORY.md"),
                "MEMPALACE_GROK_SESSIONS_ROOT": str(root / "sessions"),
                "MEMPALACE_CONTINUITY_ALLOWED_ROOTS": str(root / "allowed"),
                "MEMPALACE_CONTINUITY_TAIL_DIR": str(root / "tails"),
            }
            with patch.dict(os.environ, env, clear=False):
                _output, receipt = run_event(
                    {
                        "hookEventName": "PostCompact",
                        "sessionId": "sess",
                        "transcriptPath": str(session / "chat_history.jsonl"),
                        "cwd": str(root),
                    }
                )
                self.assertEqual(receipt["status"], "postcompact_taped")
                self.assertIsNotNone(needs_recall_record())
                recall = (root / "hook_state" / "RECALL.md").read_text(encoding="utf-8")
                self.assertIn("by_hash", recall)
                self.assertTrue((root / "MEMORY.md").is_file())


class VerbatimLogTests(unittest.TestCase):
    def test_extract_and_dedup(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            env = {"MEMPALACE_HOOK_STATE_DIR": str(root)}
            text = "<user_query>\nkeep this nuance\n</user_query>"
            with patch.dict(os.environ, env, clear=False):
                self.assertEqual(extract_user_queries(text), ["keep this nuance"])
                n1 = append_verbatim_users(
                    ["keep this nuance"], session_id="s", source="t"
                )
                n2 = append_verbatim_users(
                    ["keep this nuance"], session_id="s", source="t"
                )
                self.assertEqual(n1, 1)
                self.assertEqual(n2, 0)

    def test_extract_skips_system_and_overlong_spans(self):
        huge = "<user_query>\n" + ("x" * 40000) + "\n</user_query>"
        system = "<user_query>\n<user_info>nope</user_info>\n</user_query>"
        self.assertEqual(extract_user_queries(huge), [])
        self.assertEqual(extract_user_queries(system), [])

    def test_harvest_keeps_assistant_and_reasoning_not_just_user(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            chat = root / "chat_history.jsonl"
            rows = [
                {
                    "type": "user",
                    "content": [
                        {"type": "text", "text": "<user_query>\nlossless thoughts too\n</user_query>"}
                    ],
                },
                {
                    "type": "reasoning",
                    "summary": [
                        {"type": "summary_text", "text": "need assistant replies not just user words"}
                    ],
                    "encrypted_content": "not-plaintext",
                },
                {"type": "assistant", "content": "keeping the reasoning and the reply"},
            ]
            chat.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            env = {"MEMPALACE_HOOK_STATE_DIR": str(root / "hook_state")}
            with patch.dict(os.environ, env, clear=False):
                added = harvest_conversation_from_jsonl(chat, session_id="s")
                self.assertEqual(added, 3)
                tape = conversation_tape_path().read_text(encoding="utf-8")
                self.assertIn("lossless thoughts too", tape)
                self.assertIn("need assistant replies not just user words", tape)
                self.assertIn("keeping the reasoning and the reply", tape)
                self.assertNotIn("not-plaintext", tape)
                self.assertEqual(harvest_conversation_from_jsonl(chat, session_id="s"), 0)


if __name__ == "__main__":
    unittest.main()
