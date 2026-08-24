from __future__ import annotations
from contextlib import contextmanager
from hashlib import sha256
from io import StringIO
import importlib.util
import json
import os
from pathlib import Path
import re
from types import ModuleType
from typing import Iterator
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "tools/harness_templates/hooks"
METHOD_GUARD_PATH = HOOKS / "method_guard.py"
NO_MEMO = "You are a subagent. Don't run memo."
CHUNK_END = "<<<METHOD_PACKET_CHUNK_END>>>"
PACKET_END = "<<<METHOD_PACKET_END"
ROUTE_METHODS = {
    "investigation": ["how", "why"],
    "architecture": ["architect", "arena", "codebase-design"],
    "implementation": ["tdd", "implement"],
    "review": ["code-review"],
}
STANDING_LAWS = ["unlazy", "clean-code-for-agents", "unslop", "writing-for-agents"]
PRINCIPLES = """principle-fix-root-causes principle-foundational-thinking
principle-redesign-from-first-principles principle-subtract-before-you-add principle-model-the-domain
principle-boundary-discipline principle-make-operations-idempotent principle-separate-before-serializing-shared-state
principle-encode-lessons-in-structure principle-sequence-verifiable-units principle-prove-it-works
principle-minimize-reader-load""".split()
def load_module(name: str, path: Path) -> ModuleType | None:
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
method_guard = load_module("method_guard", METHOD_GUARD_PATH)


def method_chunk_body(response: str) -> str:
    try:
        _, remainder = response.split("\n", 1)
        body, _ = remainder.split(f"\n{CHUNK_END}\n", 1)
    except ValueError as error:
        raise AssertionError(f"malformed engage chunk {response!r}") from error
    return body


def hook_payload(event: str, **extra: object) -> dict[str, object]:
    return {
        "hook_event_name": event,
        "session_id": "session-fixture",
        "turn_id": "turn-fixture",
        **extra,
    }
def block_reason(output: StringIO) -> str:
    response = json.loads(output.getvalue())
    specific = response.get("hookSpecificOutput", {})
    return str(specific.get("permissionDecisionReason", response.get("reason", "")))
class MethodFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.repo = root / "repo"
        self.state = root / "external-state"
        self.pstack = root / "pstack"
        self.scope = "fixture"
        self.sources = self._write_sources()
        self.plan_sources = self._write_plan_sources()
        self.contract = self._contract()
    def _write(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
    def _write_sources(self) -> dict[str, Path]:
        sources = {
            "implement-flow": self._write(
                self.repo / ".agents/skills/implement-flow/SKILL.md",
                "implement-flow canonical router\n",
            ),
            "poteto-mode": self._write(
                self.pstack / "skills/poteto-mode/SKILL.md",
                "poteto mode\nPrinciples\nall twenty-one entries\n",
            ),
            "playbook:bug-fix": self._write(
                self.pstack / "skills/poteto-mode/playbooks/bug-fix.md",
                "pristine bug fix playbook\n",
            ),
        }
        for name in [*STANDING_LAWS, *sum(ROUTE_METHODS.values(), []), *PRINCIPLES]:
            sources[name] = self._write(
                self.repo / f".agents/skills/{name}/SKILL.md",
                f"complete canonical source for {name}\n",
            )
        return sources
    def _write_plan_sources(self) -> dict[str, Path]:
        return {
            "plan-flow": self._write(
                self.repo / ".agents/skills/plan-flow/SKILL.md", "plan-flow canonical router\n"
            ),
            "playbook:multi-phase-plan": self._write(
                self.pstack / "skills/poteto-mode/playbooks/multi-phase-plan.md",
                "complete pinned multi-phase plan playbook\n",
            ),
            "reference:plan": self._write(
                self.pstack / "skills/poteto-mode/references/plan.md",
                "complete pinned Poteto plan reference\n",
            ),
        }
    def _contract(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "route": "implement-flow",
            "playbook": "bug-fix",
            "outer_method": ["implement-flow", "poteto-mode", "playbook:bug-fix"],
            "nested_method": ROUTE_METHODS,
            "standing_laws": STANDING_LAWS,
            "testing_choice": {"selected": "tdd", "reason": "local regression seam"},
            "engagement": {
                "mode": "exact-source-packet",
                "required": ["router", "poteto-mode-with-principles-index", "selected-playbook",
                             "standing-laws", "nested-method-sources", "selected-principle-leaves"],
                "rearm_after": ["compact", "clear", "source-digest-change"],
            },
            "principles": [
                {"name": name, "decision": f"decision for {name}", "evidence": "src/app.py"}
                for name in PRINCIPLES
            ],
            "owns": ["src/**", "tests/**"],
            "gates": f".unlazy/{self.scope}/GATES.md",
            "model_policy": {
                "routine_implementation_model": "gpt-5.6-sol",
                "routine_implementation_reasoning": "medium",
                "higher_reasoning_for": ["architecture"],
            },
        }
    def write_contract(self) -> Path:
        return self._write(
            self.repo / f".unlazy/{self.scope}/METHOD.json",
            json.dumps(self.contract, sort_keys=True),
        )
    def write_gates(self) -> Path:
        return self._write(
            self.repo / f".unlazy/{self.scope}/GATES.md",
            "# Gates\n\n- [ ] G1\n  CHECK: python test.py\n  EXPECT: OK\n",
        )
    @contextmanager
    def environment(self) -> Iterator[None]:
        values = {
            "CODEX_METHOD_REPO_ROOT": str(self.repo),
            "CODEX_METHOD_STATE_ROOT": str(self.state),
            "CODEX_METHOD_PSTACK_ROOT": str(self.pstack),
        }
        with patch.dict(os.environ, values, clear=False):
            yield
class MethodGuardTests(unittest.TestCase):
    def require_guard(self) -> ModuleType:
        self.assertIsNotNone(
            method_guard,
            f"missing planned method guard at {METHOD_GUARD_PATH}",
        )
        return method_guard
    def call_guard(
        self,
        arguments: list[str],
        payload: dict[str, object],
    ) -> tuple[int, StringIO, StringIO]:
        guard = self.require_guard()
        output = StringIO()
        errors = StringIO()
        status = guard.main(arguments, StringIO(json.dumps(payload)), output, errors)
        return status, output, errors
    def activate(self, fixture: MethodFixture, route: str = "implement-flow") -> None:
        self.call_guard(
            ["user-prompt-submit"],
            hook_payload(
                "UserPromptSubmit",
                prompt=f"${route} fix it",
                cwd=str(fixture.repo),
            ),
        )

    def call_direct_guard(self, arguments: list[str]) -> StringIO:
        guard = self.require_guard()
        output = StringIO()
        errors = StringIO()
        status = guard.main(arguments, StringIO(), output, errors)
        self.assertEqual(status, 0)
        self.assertEqual(errors.getvalue(), "")
        return output

    def engage(self, fixture: MethodFixture) -> StringIO:
        chunks: list[str] = []
        for number in range(1, 33):
            arguments = ["engage", fixture.scope]
            if number > 1:
                arguments.append(str(number))
            response = self.call_direct_guard(arguments).getvalue()
            chunks.append(method_chunk_body(response))
            if PACKET_END in response:
                return StringIO("".join(chunks))
        raise AssertionError(f"engage exceeded {len(chunks)} chunks")
    def prepare_engaged(self, fixture: MethodFixture) -> None:
        fixture.write_contract()
        fixture.write_gates()
        self.activate(fixture)
        self.engage(fixture)
    @staticmethod
    def production_patch(fixture: MethodFixture) -> dict[str, object]:
        return hook_payload(
            "PreToolUse",
            cwd=str(fixture.repo),
            tool_name="apply_patch",
            tool_input={"patch": "*** Add File: src/app.py\n+changed\n"},
        )
    def test_hook_inventory_has_one_policy_owner_and_keeps_lifecycle(self) -> None:
        expected = {
            "SessionStart",
            "UserPromptSubmit",
            "PreToolUse",
            "SubagentStart",
            "SubagentStop",
            "PreCompact",
            "SessionEnd",
            "Stop",
        }
        for config_path in [ROOT / ".codex/hooks.json", ROOT / "tools/harness_templates/hooks.json"]:
            hooks = json.loads(config_path.read_text(encoding="utf-8"))["hooks"]
            self.assertEqual(set(hooks), expected, config_path)
            self.assertEqual(len(hooks["Stop"]), 1, config_path)
            command = hooks["Stop"][0]["hooks"][0]["command"]
            self.assertIn("method_guard.py stop", command)
            self.assertIn("memory_ledger_hooks.py", hooks["SessionStart"][0]["hooks"][0]["command"])
    def test_plan_packet_is_complete_and_production_patch_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            fixture.contract["route"] = "plan-flow"
            fixture.contract["playbook"] = "multi-phase-plan"
            fixture.contract["outer_method"] = [
                "plan-flow", "poteto-mode", "playbook:multi-phase-plan"
            ]
            fixture.write_contract()
            fixture.write_gates()
            with fixture.environment():
                self.activate(fixture, "plan-flow")
                packet_output = self.engage(fixture)
                _, output, _ = self.call_guard(
                    ["pre-tool-use"], self.production_patch(fixture)
                )
            packet = packet_output.getvalue()
            required = [fixture.sources["poteto-mode"], *fixture.plan_sources.values()]
            for source in required:
                digest = sha256(source.read_bytes()).hexdigest()
                marker = f"path={source} sha256={digest}"
                self.assertIn(marker, packet)
                self.assertIn(source.read_text(encoding="utf-8"), packet)
            self.assertIn("plan-flow", block_reason(output))
    def test_bash_requires_command_and_non_read_only_calls_require_a_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            with fixture.environment():
                _, allowed, _ = self.call_guard(
                    ["pre-tool-use"],
                    hook_payload("PreToolUse", tool_name="Bash", tool_input={"command": "git status"}),
                )
                # A read passes under either key, and a command that can change
                # something needs the method under either key. The two used to
                # behave differently, which was an accident of the old parser.
                for tool_input in ({"cmd": "git status"}, {"command": "git status"}):
                    _, passed, _ = self.call_guard(
                        ["pre-tool-use"],
                        hook_payload("PreToolUse", tool_name="Bash", tool_input=tool_input),
                    )
                    self.assertEqual(json.loads(passed.getvalue()), {})
                for tool_input in ({"cmd": "python test.py"}, {"command": "python test.py"}):
                    _, denied, _ = self.call_guard(
                        ["pre-tool-use"],
                        hook_payload("PreToolUse", tool_name="Bash", tool_input=tool_input),
                    )
                    self.assertIn("explicit", block_reason(denied).lower())
            self.assertEqual(json.loads(allowed.getvalue()), {})
    def test_absolute_method_artifacts_bootstrap_and_edits_revoke_readiness(self) -> None:
        for artifact in ("METHOD.json", "GATES.md"):
            with self.subTest(artifact), tempfile.TemporaryDirectory() as raw:
                fixture = MethodFixture(Path(raw))
                path = fixture.repo / f".unlazy/{fixture.scope}/{artifact}"
                patch_payload = hook_payload(
                    "PreToolUse", cwd=str(fixture.repo), tool_name="apply_patch",
                    tool_input={"patch": f"*** Update File: {path}\n+changed\n"},
                )
                with fixture.environment():
                    self.activate(fixture)
                    _, bootstrap, _ = self.call_guard(["pre-tool-use"], patch_payload)
                    self.assertEqual(json.loads(bootstrap.getvalue()), {})
                    self.prepare_engaged(fixture)
                    _, edit, _ = self.call_guard(["pre-tool-use"], patch_payload)
                    self.assertEqual(json.loads(edit.getvalue()), {})
                    _, denied, _ = self.call_guard(
                        ["pre-tool-use"], self.production_patch(fixture)
                    )
                self.assertIn("edit", block_reason(denied).lower())
    def test_subagent_start_state_failure_returns_developer_context(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            with fixture.environment():
                _, output, _ = self.call_guard(
                    ["subagent-start"], hook_payload("SubagentStart", cwd=str(fixture.repo))
                )
        response = json.loads(output.getvalue())
        self.assertNotIn("decision", response)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Method guard state error", context)
        self.assertIn("report this error to the parent", context)
    def test_implement_route_requires_contract_gates_and_current_packet(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            write = self.production_patch(fixture)
            with fixture.environment():
                self.activate(fixture)
                _, output, _ = self.call_guard(["pre-tool-use"], write)
                self.assertIn("METHOD.json", block_reason(output))
                fixture.write_contract()
                _, output, _ = self.call_guard(["pre-tool-use"], write)
                self.assertIn("GATES.md", block_reason(output))
                fixture.write_gates()
                _, output, _ = self.call_guard(["pre-tool-use"], write)
                self.assertIn("engage", block_reason(output).lower())
                self.engage(fixture)
                _, output, _ = self.call_guard(["pre-tool-use"], write)
            self.assertEqual(json.loads(output.getvalue()), {})
    def test_engagement_packet_has_exact_complete_sources_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            with fixture.environment():
                fixture.write_contract()
                fixture.write_gates()
                self.activate(fixture)
                output = self.engage(fixture)
            packet = output.getvalue()
            names = set(re.findall(r"<<<METHOD_SOURCE_START name=([^ ]+)", packet))
            self.assertEqual(names, set(fixture.sources))
            for name, source in fixture.sources.items():
                source_bytes = source.read_bytes()
                digest = sha256(source_bytes).hexdigest()
                marker = f"name={name} path={source} sha256={digest}"
                self.assertIn(marker, packet, name)
                self.assertIn(source_bytes.decode(), packet, name)

    def test_digest_change_rearms_and_compact_restores_current_packet(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            write = self.production_patch(fixture)
            with fixture.environment():
                self.prepare_engaged(fixture)
                fixture.sources["implement-flow"].write_text("changed router\n", encoding="utf-8")
                _, changed, _ = self.call_guard(["pre-tool-use"], write)
                self.assertIn("source digest", block_reason(changed).lower())
                direct = self.engage(fixture)
                _, start, _ = self.call_guard(
                    ["session-start"],
                    hook_payload("SessionStart", source="compact", cwd=str(fixture.repo)),
                )
                _, resumed, _ = self.call_guard(["pre-tool-use"], write)
            context = json.loads(start.getvalue())["hookSpecificOutput"]["additionalContext"]
            self.assertEqual(context, direct.getvalue())
            self.assertEqual(json.loads(resumed.getvalue()), {})
    def test_subagent_launch_requires_exact_brief_scope_acceptance_and_model(self) -> None:
        valid = (
            f"{NO_MEMO}\n\nOwn only `tests/test_widget.py`.\n"
            "You are not alone in the codebase.\n"
            "Do not revert others' edits.\n"
            "Acceptance check: run `python -m unittest tests.test_widget`; expect `OK`."
        )
        invalid = {
            "missing memo": valid.replace(f"{NO_MEMO}\n\n", ""),
            "duplicate memo": f"{NO_MEMO}\n{valid}",
            "missing ownership": valid.replace("Own only `tests/test_widget.py`.\n", ""),
            "missing acceptance": valid.split("\nAcceptance check:")[0],
            "missing shared-codebase warning": valid.replace(
                "You are not alone in the codebase.\n", ""
            ),
            "missing preserve-edits warning": valid.replace(
                "Do not revert others' edits.\n", ""
            ),
        }
        with tempfile.TemporaryDirectory() as raw:
            fixture = MethodFixture(Path(raw))
            with fixture.environment():
                self.prepare_engaged(fixture)
                for label, brief in invalid.items():
                    with self.subTest(label):
                        _, output, _ = self.call_guard(
                            ["pre-tool-use"], self._spawn_payload(fixture, brief)
                        )
                        self.assertTrue(block_reason(output), label)
                _, wrong_model, _ = self.call_guard(
                    ["pre-tool-use"], self._spawn_payload(fixture, valid, model="gpt-5.6-luna")
                )
                self.assertIn("gpt-5.6-sol", block_reason(wrong_model))
                _, output, _ = self.call_guard(
                    ["pre-tool-use"], self._spawn_payload(fixture, valid)
                )
            self.assertEqual(json.loads(output.getvalue()), {})
    @staticmethod
    def _spawn_payload(
        fixture: MethodFixture,
        brief: str,
        model: str = "gpt-5.6-sol",
    ) -> dict[str, object]:
        return hook_payload(
            "PreToolUse",
            cwd=str(fixture.repo),
            tool_name="collaboration.spawn_agent",
            tool_input={
                "message": brief,
                "model": model,
                "reasoning_effort": "medium",
                "task_name": "widget_tests",
            },
        )
    def test_stop_runs_unlazy_before_method_evidence_and_unslop(self) -> None:
        guard = self.require_guard()
        calls: list[str] = []
        unlazy_block = {"decision": "block", "reason": "unlazy exact block"}
        def unlazy(_: dict[str, object]) -> dict[str, object]:
            calls.append("unlazy")
            return unlazy_block
        evidence_result = ["missing method evidence"]
        def evidence(_: dict[str, object]) -> str | None:
            calls.append("evidence")
            return evidence_result[0]
        def unslop(_: str) -> str | None:
            calls.append("unslop")
            return "em dash"

        def clean_code(_: object) -> str | None:
            calls.append("clean-code")
            return None
        with (
            patch.object(guard, "run_unlazy_stop", unlazy, create=True),
            patch.object(guard, "method_evidence_violation", evidence, create=True),
            patch.object(guard, "unslop_violation", unslop, create=True),
        ):
            _, output, _ = self.call_guard(
                ["stop"], hook_payload("Stop", last_assistant_message="done")
            )
        self.assertEqual(json.loads(output.getvalue()), unlazy_block)
        self.assertEqual(calls, ["unlazy"])
        calls.clear()
        evidence_result[0] = None
        with (
            patch.object(guard, "run_unlazy_stop", lambda _: calls.append("unlazy") or {}, create=True),
            patch.object(guard, "method_evidence_violation", evidence, create=True),
            patch.object(guard, "unslop_violation", unslop, create=True),
            patch.object(guard, "clean_code_violation", clean_code, create=True),
        ):
            _, output, _ = self.call_guard(
                ["stop"], hook_payload("Stop", last_assistant_message="bad prose")
            )
        self.assertEqual(calls, ["unlazy", "evidence", "clean-code", "unslop"])
        self.assertIn("em dash", json.loads(output.getvalue())["reason"])
if __name__ == "__main__":
    unittest.main()
