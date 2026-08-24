from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.test_agent_method_guard import MethodFixture, hook_payload, method_guard


ROOT = Path(__file__).resolve().parents[1]
UNLAZY_PIN = "754d9a68109e39b836cc72a39fb9a823f9d6b613"
UNLAZY_SCRIPTS = ROOT / f"vendor/agent-sources/unlazy/{UNLAZY_PIN}/scripts"
PACKET_END = "<<<METHOD_PACKET_END"


def call_guard(arguments: list[str], payload: dict[str, object]) -> dict[str, object]:
    output = StringIO()
    status = method_guard.main(
        arguments, StringIO(json.dumps(payload)), output, StringIO()
    )
    if status != 0:
        raise AssertionError(f"guard exited {status}, expected 0")
    return json.loads(output.getvalue())


def install_unlazy(fixture: MethodFixture) -> None:
    destination = fixture.repo / f"vendor/agent-sources/unlazy/{UNLAZY_PIN}/scripts"
    shutil.copytree(UNLAZY_SCRIPTS, destination)


def engage_fixture(fixture: MethodFixture) -> None:
    fixture.write_contract()
    gates = fixture.write_gates()
    gates.write_text(
        "# Gates\n\n- [ ] G1: fixture remains unmet\n  EVIDENCE: pending\n",
        encoding="utf-8",
    )
    install_unlazy(fixture)
    call_guard([
        "user-prompt-submit",
    ], hook_payload(
        "UserPromptSubmit", prompt="$implement-flow fix it", cwd=str(fixture.repo)
    ))
    for number in range(1, 33):
        arguments = ["engage", fixture.scope]
        if number > 1:
            arguments.append(str(number))
        output = StringIO()
        status = method_guard.main(arguments, StringIO(), output, StringIO())
        if status != 0:
            raise AssertionError(f"guard exited {status}, expected 0")
        if PACKET_END in output.getvalue():
            return
    raise AssertionError(
        f"engage final response missing {PACKET_END!r}: {output.getvalue()[:200]!r}"
    )


def stop_payload(fixture: MethodFixture, session_id: str, message: str) -> dict[str, object]:
    return hook_payload(
        "Stop", session_id=session_id, cwd=str(fixture.repo),
        last_assistant_message=message, stop_hook_active=False,
    )


def patch_payload(fixture: MethodFixture, path: Path) -> dict[str, object]:
    return hook_payload(
        "PreToolUse", cwd=str(fixture.repo), tool_name="apply_patch",
        tool_input={"patch": f"*** Update File: {path}\n+changed\n"},
    )


class ScopeRearmTests(unittest.TestCase):
    def test_unrelated_scope_artifact_does_not_rearm_active_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            unrelated = fixture.repo / ".unlazy/other-scope/GATES.md"
            with fixture.environment():
                engage_fixture(fixture)
                self.assertEqual(call_guard(["pre-tool-use"], patch_payload(fixture, unrelated)), {})
                response = call_guard(
                    ["pre-tool-use"], patch_payload(fixture, fixture.repo / "src/app.py")
                )
        self.assertEqual(response, {})


class StopScopeTests(unittest.TestCase):
    def test_unbound_sessions_ignore_one_or_many_scopes(self) -> None:
        for extra_scope in (False, True):
            with self.subTest(extra_scope=extra_scope), tempfile.TemporaryDirectory() as raw:
                fixture = MethodFixture(Path(raw))
                with fixture.environment():
                    engage_fixture(fixture)
                    if extra_scope:
                        self._write_extra_scope(fixture)
                    response = call_guard(
                        ["stop"], stop_payload(fixture, "unbound-session", "Work is complete.")
                    )
                self.assertEqual(response, {})

    def test_bound_session_with_unmet_gates_still_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            with fixture.environment():
                engage_fixture(fixture)
                response = call_guard(
                    ["stop"], stop_payload(fixture, "session-fixture", "Work is complete.")
                )
        self.assertEqual(response.get("decision"), "block")
        self.assertIn(fixture.scope, str(response.get("reason")))

    @staticmethod
    def _write_extra_scope(fixture: MethodFixture) -> None:
        directory = fixture.repo / ".unlazy/other-scope"
        directory.mkdir(parents=True)
        (directory / "GATES.md").write_text(
            "# Gates\n\n- [ ] G1\n  EVIDENCE: pending\n", encoding="utf-8"
        )
        (directory / "session").write_text("other-session\n", encoding="utf-8")


class StopCounterTests(unittest.TestCase):
    def test_subagent_blocks_do_not_spend_the_parent_limit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            with fixture.environment():
                engage_fixture(fixture)
                for _ in range(3):
                    child = stop_payload(fixture, "session-fixture", "Of course! child done.")
                    child.update({"hook_event_name": "SubagentStop", "agent_id": "child-1"})
                    self.assertEqual(call_guard(["subagent-stop"], child).get("decision"), "block")
                parent = stop_payload(fixture, "session-fixture", "Work is complete.")
                parent["stop_hook_active"] = True
                response = call_guard(["stop"], parent)
        self.assertEqual(response.get("decision"), "block")
        self.assertNotIn("released", str(response.get("systemMessage", "")).lower())

    def test_parent_limit_still_releases_after_three_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            with fixture.environment():
                engage_fixture(fixture)
                parent = stop_payload(fixture, "session-fixture", "Work is complete.")
                for _ in range(3):
                    self.assertEqual(call_guard(["stop"], parent).get("decision"), "block")
                parent["stop_hook_active"] = True
                response = call_guard(["stop"], parent)
        self.assertIn("released", str(response.get("systemMessage", "")).lower())


if __name__ == "__main__":
    unittest.main()
