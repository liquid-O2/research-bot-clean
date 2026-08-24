from __future__ import annotations

from io import StringIO
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from tests.test_agent_method_guard import (
    MethodFixture,
    NO_MEMO,
    ROOT,
    block_reason,
    hook_payload,
    method_guard,
)


CHUNK_END = "<<<METHOD_PACKET_CHUNK_END>>>"
PACKET_END = "<<<METHOD_PACKET_END"
PACKET_START = "<<<METHOD_PACKET_START"
MEMORY_HOOK_PATH = ROOT / "tools/harness_templates/hooks/memory_ledger_hooks.py"


def load_memory_hook(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, MEMORY_HOOK_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load memory hook from {MEMORY_HOOK_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def call_guard(arguments: list[str], payload: dict[str, object] | None) -> dict[str, object] | str:
    output = StringIO()
    source = "" if payload is None else json.dumps(payload)
    status = method_guard.main(arguments, StringIO(source), output, StringIO())
    if status != 0:
        raise AssertionError(f"guard exited {status}, expected 0")
    raw = output.getvalue()
    return json.loads(raw) if payload is not None else raw


def activate(fixture: MethodFixture) -> None:
    call_guard(
        ["user-prompt-submit"],
        hook_payload(
            "UserPromptSubmit", prompt="$implement-flow fix it", cwd=str(fixture.repo)
        ),
    )


def production_patch(fixture: MethodFixture) -> dict[str, object]:
    return hook_payload(
        "PreToolUse", cwd=str(fixture.repo), tool_name="apply_patch",
        tool_input={"patch": "*** Add File: src/app.py\n+changed\n"},
    )


def chunk_body(response: str) -> str:
    try:
        _, remainder = response.split("\n", 1)
        body, _ = remainder.split(f"\n{CHUNK_END}\n", 1)
    except ValueError as error:
        raise AssertionError(f"malformed direct engage chunk {response!r}") from error
    return body


def collect_direct_packet(fixture: MethodFixture) -> str:
    chunks: list[str] = []
    response = call_guard(["engage", fixture.scope], None)
    repeated = call_guard(["engage", fixture.scope], None)
    if response != repeated:
        actual_header = str(repeated).splitlines()[:1]
        expected_header = str(response).splitlines()[:1]
        raise AssertionError(f"repeat returned {actual_header!r}, expected {expected_header!r}")
    for chunk_number in range(1, 33):
        if not isinstance(response, str):
            raise AssertionError(f"direct engage returned {type(response).__name__}, expected text")
        response_bytes = len(response.encode())
        if response_bytes > 25_000:
            raise AssertionError(f"direct engage returned {response_bytes} bytes, expected at most 25000")
        chunks.append(chunk_body(response))
        verdict = call_guard(["pre-tool-use"], production_patch(fixture))
        if PACKET_END in response:
            if verdict != {}:
                raise AssertionError(f"final engage chunk left writes blocked: {verdict}")
            repeated = call_guard(["engage", fixture.scope, str(chunk_number)], None)
            if response != repeated:
                raise AssertionError(f"repeating final engage chunk {chunk_number} changed output")
            return "".join(chunks)
        reason = block_reason(StringIO(json.dumps(verdict)))
        if not isinstance(verdict, dict) or "entered" not in reason:
            raise AssertionError(f"partial engage chunk allowed a write: {verdict}")
        next_number = chunk_number + 1
        expected = f"engage {fixture.scope} {next_number}"
        if expected not in response:
            raise AssertionError(f"chunk {chunk_number} omitted next command {expected!r}")
        response = call_guard(["engage", fixture.scope, str(next_number)], None)
    raise AssertionError(f"direct engage returned {len(chunks)} chunks, expected a final marker")


class _FailReconciliation:
    def __init__(self, message: str) -> None:
        self.message = message

    def __call__(self) -> None:
        raise RuntimeError(f"reconciliation failed with {self.message}")


class MethodContextLifecycleTests(unittest.TestCase):
    def test_codex_repository_override_selects_the_memory_ledger_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex_root = Path(raw) / "codex-repo"
            claude_root = Path(raw) / "claude-repo"
            environment = {
                "CODEX_METHOD_REPO_ROOT": str(codex_root),
                "CLAUDE_METHOD_REPO_ROOT": str(claude_root),
            }
            with patch.dict(os.environ, environment, clear=False):
                module = load_memory_hook("codex_memory_ledger_override_test")
        self.assertEqual(module.ROOT, codex_root)

    def test_claude_repository_override_remains_available_to_the_shared_hook(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            claude_root = Path(raw) / "claude-repo"
            environment = {
                "CODEX_METHOD_REPO_ROOT": "",
                "CLAUDE_METHOD_REPO_ROOT": str(claude_root),
            }
            with patch.dict(os.environ, environment, clear=False):
                module = load_memory_hook("claude_memory_ledger_override_test")
        self.assertEqual(module.ROOT, claude_root)

    def test_subagent_stop_defers_archive_until_task_complete(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "archive"
            transcript = root / "agent.jsonl"
            initial_bytes = b'{"ordinal":13,"type":"event_msg","payload":{"type":"token_count"}}\n'
            terminal_bytes = (
                b'{"ordinal":14,"type":"event_msg","payload":'
                b'{"type":"task_complete","turn_id":"turn-fixture"}}\n'
            )
            transcript.write_bytes(initial_bytes)
            payload = hook_payload(
                "SubagentStop",
                cwd=str(root),
                agent_id="child-fixture",
                agent_transcript_path=str(transcript),
            )
            with patch.dict(
                os.environ,
                {"CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(archive)},
                clear=False,
            ):
                module = load_memory_hook("codex_subagent_archive_test")
                output = StringIO()
                errors = StringIO()
                status = module.main(
                    ["subagent-stop"], StringIO(json.dumps(payload)), output, errors
                )
                pending = list((archive / "pending").glob("*.json"))
                objects_before_terminal = list((archive / "objects").rglob("*.jsonl"))
                transcript.write_bytes(initial_bytes + terminal_bytes)
                parent = root / "parent.jsonl"
                parent.write_bytes(b"parent transcript\n")
                end_output = StringIO()
                end_errors = StringIO()
                end_status = module.main(
                    ["session-end"],
                    StringIO(json.dumps(hook_payload(
                        "SessionEnd", cwd=str(root), transcript_path=str(parent)
                    ))),
                    end_output,
                    end_errors,
                )
            final_bytes = transcript.read_bytes()
            digest = sha256(final_bytes).hexdigest()
            child_object = archive / "objects" / digest[:2] / f"{digest}.jsonl"
            child_bytes = child_object.read_bytes() if child_object.is_file() else b""
            pending_after = list((archive / "pending").glob("*.json"))
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue()), {})
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(len(pending), 1)
        self.assertEqual(objects_before_terminal, [])
        self.assertEqual(end_status, 0)
        self.assertEqual(json.loads(end_output.getvalue()), {})
        self.assertEqual(end_errors.getvalue(), "")
        self.assertEqual(child_bytes, final_bytes)
        self.assertEqual(pending_after, [])

    def test_claude_subagent_stop_archives_a_complete_transcript_without_turn_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "archive"
            transcript = root / "claude-child.jsonl"
            final_bytes = b'{"type":"assistant","message":"done"}\n'
            transcript.write_bytes(final_bytes)
            payload = {
                "hook_event_name": "SubagentStop",
                "session_id": "claude-session",
                "agent_id": "claude-child",
                "agent_transcript_path": str(transcript),
                "cwd": str(root),
            }
            with patch.dict(
                os.environ,
                {"CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(archive)},
                clear=False,
            ):
                module = load_memory_hook("claude_subagent_archive_test")
                output = StringIO()
                errors = StringIO()
                status = module.main(
                    ["subagent-stop"], StringIO(json.dumps(payload)), output, errors
                )
            digest = sha256(final_bytes).hexdigest()
            archived = archive / "objects" / digest[:2] / f"{digest}.jsonl"
            archived_bytes = archived.read_bytes() if archived.is_file() else b""

        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue()), {})
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(archived_bytes, final_bytes)

    def test_child_reconciliation_failure_does_not_hide_session_context(self) -> None:
        module = load_memory_hook("codex_child_reconciliation_failure_test")
        payload = hook_payload("SessionStart", cwd=str(ROOT), source="startup")
        output = StringIO()
        errors = StringIO()
        actions = module._TranscriptActions(
            module.archive_transcript,
            module.defer_transcript,
            _FailReconciliation("damaged pending marker"),
        )
        with patch.object(module, "ledger_tail", return_value="lasting memory"):
            status = module.main(
                ["session-start"], StringIO(json.dumps(payload)), output, errors, actions
            )
        response = json.loads(output.getvalue())
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(status, 0)
        self.assertIn("lasting memory", context)
        self.assertIn("damaged pending marker", errors.getvalue())
        self.assertNotIn("continue", response)

    def test_direct_engage_needs_no_stdin_and_readies_only_after_final_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            fixture.write_contract()
            fixture.write_gates()
            fixture.sources["implement-flow"].write_text("exact router\n" + "x" * 40_000)
            with fixture.environment():
                activate(fixture)
                packet = collect_direct_packet(fixture)
        self.assertIn(PACKET_START, packet)
        self.assertIn(PACKET_END, packet)
        self.assertIn("exact router\n" + "x" * 40_000, packet)

    def test_invalid_direct_chunk_keeps_an_existing_ready_record(self) -> None:
        invalid = (("0",), ("nope",), ("999",), ("1", "extra"))
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            fixture.write_contract()
            fixture.write_gates()
            with fixture.environment():
                activate(fixture)
                for suffix in invalid:
                    collect_direct_packet(fixture)
                    response = call_guard(["engage", fixture.scope, *suffix], None)
                    self.assertIn("rejected", response)
                    self.assertEqual(call_guard(["pre-tool-use"], production_patch(fixture)), {})

    def test_compact_session_start_injects_complete_packet_and_restores_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            fixture.write_contract()
            fixture.write_gates()
            with fixture.environment():
                activate(fixture)
                direct_packet = collect_direct_packet(fixture)
                response = call_guard(
                    ["session-start"],
                    hook_payload("SessionStart", source="compact", cwd=str(fixture.repo)),
                )
                write = call_guard(["pre-tool-use"], production_patch(fixture))
        self.assertIsInstance(response, dict)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(context, direct_packet)
        self.assertEqual(write, {})

    def test_subagent_start_injects_complete_packet_and_no_memory_rule(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            fixture.write_contract()
            fixture.write_gates()
            with fixture.environment():
                activate(fixture)
                direct_packet = collect_direct_packet(fixture)
                response = call_guard(
                    ["subagent-start"],
                    hook_payload(
                        "SubagentStart", cwd=str(fixture.repo), agent_id="child-fixture"
                    ),
                )
        self.assertIsInstance(response, dict)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(context, f"{NO_MEMO}\n\n{direct_packet}")

    def test_lifecycle_carries_a_packet_above_the_legacy_inline_cap(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            fixture.write_contract()
            fixture.write_gates()
            fixture.sources["implement-flow"].write_text(
                "large exact source\n" + "x" * 190_000, encoding="utf-8"
            )
            with fixture.environment():
                activate(fixture)
                direct_packet = collect_direct_packet(fixture)
                response = call_guard(
                    ["subagent-start"],
                    hook_payload(
                        "SubagentStart", cwd=str(fixture.repo), agent_id="child-fixture"
                    ),
                )
                compact = call_guard(
                    ["session-start"],
                    hook_payload("SessionStart", source="compact", cwd=str(fixture.repo)),
                )
        self.assertGreater(len(direct_packet.encode()), 192_000)
        self.assertIsInstance(response, dict)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(context, f"{NO_MEMO}\n\n{direct_packet}")
        self.assertIsInstance(compact, dict)
        compact_context = compact["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(compact_context, direct_packet)


if __name__ == "__main__":
    unittest.main()
