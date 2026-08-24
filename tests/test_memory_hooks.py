from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_agent_method_guard import MethodFixture, block_reason, hook_payload, method_guard


CHUNK_END = "<<<METHOD_PACKET_CHUNK_END>>>"
PACKET_END = "<<<METHOD_PACKET_END"
PACKET_START = "<<<METHOD_PACKET_START"


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
    for _ in range(32):
        response = call_guard(["engage", fixture.scope], None)
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
            return "".join(chunks)
        reason = block_reason(StringIO(json.dumps(verdict)))
        if not isinstance(verdict, dict) or "entered" not in reason:
            raise AssertionError(f"partial engage chunk allowed a write: {verdict}")
    raise AssertionError(f"direct engage returned {len(chunks)} chunks, expected a final marker")


class MethodContextLifecycleTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
