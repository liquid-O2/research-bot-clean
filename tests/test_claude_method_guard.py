#!/usr/bin/env python3
"""Prove the Claude guard reads real payloads and fails open on its own bugs.

Behaviour end to end is covered by `tools/run_method_canaries.py`, which drives
the installed hook the way the client drives it. This suite covers what canaries
cannot: that the extraction matches payloads captured from live hook runs, and
that an unexpected internal failure lets the call through instead of denying it.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import shutil
import os
from pathlib import Path
from types import ModuleType
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude/hooks"
FIXTURES = ROOT / "tests/fixtures/claude_hook_payloads"
sys.path.insert(0, str(HOOKS))


def load(name: str, path: Path) -> ModuleType | None:
    """Import one installed hook module by path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = load("claude_guard_under_test", HOOKS / "method_guard.py")
rules = load("claude_rules_under_test", HOOKS / "method_guard_rules.py")


def fixture(name: str) -> dict[str, object]:
    """Load one payload captured from a live hook run."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FixtureShapeTests(unittest.TestCase):
    """The captured payloads are the contract; the docs are not."""

    def test_every_captured_payload_is_still_readable(self) -> None:
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(payload=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn("hook_event_name", payload)
                self.assertIn("session_id", payload)

    def test_a_write_payload_yields_its_file_path(self) -> None:
        payload = fixture("PreToolUse-Write")
        targets = guard.write_targets("Write", payload["tool_input"])
        self.assertEqual(targets, [payload["tool_input"]["file_path"]])

    def test_an_edit_payload_yields_its_file_path(self) -> None:
        payload = fixture("PreToolUse-Edit")
        self.assertEqual(guard.write_targets("Edit", payload["tool_input"]),
                         [payload["tool_input"]["file_path"]])

    def test_a_batched_edit_yields_every_path(self) -> None:
        tool_input = {"edits": [{"file_path": "a.py"}, {"file_path": "b.py"}]}
        self.assertEqual(guard.write_targets("MultiEdit", tool_input), ["a.py", "b.py"])

    def test_a_read_only_bash_payload_writes_nothing(self) -> None:
        payload = fixture("PreToolUse-Bash")
        payload["tool_input"]["command"] = "ls -la /workspace"
        self.assertIsNone(guard.write_targets("Bash", payload["tool_input"]))

    def test_a_spawn_payload_exposes_its_brief_and_type(self) -> None:
        tool_input = fixture("PreToolUse-Agent")["tool_input"]
        self.assertIn("prompt", tool_input)
        self.assertIn("subagent_type", tool_input)
        self.assertIn("model", tool_input)

    def test_subagent_start_carries_no_brief(self) -> None:
        """Brief validation must live at PreToolUse, because this event has none."""
        payload = fixture("SubagentStart")
        self.assertNotIn("tool_input", payload)
        self.assertNotIn("prompt", payload)

    def test_subagent_stop_carries_the_final_message(self) -> None:
        self.assertIn("last_assistant_message", fixture("SubagentStop"))


class FailOpenTests(unittest.TestCase):
    """A guard bug must never become the next deadlock (D-108)."""

    def setUp(self) -> None:
        self.state = tempfile.mkdtemp(prefix="fail-open-")
        environment = patch.dict(os.environ, {"CLAUDE_METHOD_REPO_ROOT": str(ROOT),
                                              "CLAUDE_METHOD_STATE_ROOT": self.state})
        environment.start()
        self.addCleanup(environment.stop)
        self.addCleanup(shutil.rmtree, self.state, True)

    def test_an_unexpected_error_allows_the_call_and_warns(self) -> None:
        payload = fixture("PreToolUse-Write")
        with patch.object(guard.policy, "load_state", side_effect=RuntimeError("disk on fire")):
            response = guard.pre_tool_use(payload)
        self.assertIn("systemMessage", response)
        self.assertIn("failed open", response["systemMessage"])
        self.assertNotIn("hookSpecificOutput", response)

    def test_a_policy_violation_still_denies(self) -> None:
        payload = dict(fixture("PreToolUse-Write"))
        payload["tool_input"] = {"file_path": str(ROOT / "engine/nope.py"), "content": "x"}
        response = guard.pre_tool_use(payload)
        decision = response["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "deny")

    def test_a_repeat_stop_still_runs_its_walls(self) -> None:
        """Returning early on stop_hook_active let the second attempt ship free."""
        response = guard.stop({"stop_hook_active": True, "cwd": str(ROOT),
                               "session_id": "recurse",
                               "last_assistant_message": "Of course! Done."})
        self.assertEqual(response.get("decision"), "block")

    def test_a_repeat_subagent_stop_still_runs_its_wall(self) -> None:
        response = guard.subagent_stop({"stop_hook_active": True, "cwd": str(ROOT),
                                        "session_id": "recurse",
                                        "last_assistant_message": "Of course! Done."})
        self.assertEqual(response.get("decision"), "block")


class StopWallTests(unittest.TestCase):
    """No violation ships free, and no wall becomes a loop."""

    def setUp(self) -> None:
        self.state = tempfile.mkdtemp(prefix="stop-wall-")
        self.environment = patch.dict(os.environ, {
            "CLAUDE_METHOD_REPO_ROOT": str(ROOT),
            "CLAUDE_METHOD_STATE_ROOT": self.state})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(shutil.rmtree, self.state, True)

    def payload(self, message: str, active: bool = False) -> dict[str, object]:
        return {"hook_event_name": "Stop", "session_id": "wall", "cwd": str(ROOT),
                "last_assistant_message": message, "stop_hook_active": active}

    def test_a_repeat_attempt_is_still_checked(self) -> None:
        """The old guard returned {} whenever stop_hook_active was set."""
        response = guard.stop(self.payload("Done \N{EM DASH} all good.", active=True))
        self.assertEqual(response.get("decision"), "block")

    def test_a_turn_is_released_after_repeated_blocks(self) -> None:
        for _ in range(guard.MAX_TURN_BLOCKS):
            guard.stop(self.payload("Done \N{EM DASH} all good.", active=True))
        released = guard.stop(self.payload("Done \N{EM DASH} all good.", active=True))
        self.assertNotIn("decision", released)
        self.assertIn("released", released["systemMessage"])

    def test_a_first_attempt_is_never_released(self) -> None:
        for _ in range(guard.MAX_TURN_BLOCKS + 2):
            response = guard.stop(self.payload("Done \N{EM DASH} all good."))
            self.assertEqual(response.get("decision"), "block")

    def test_a_new_prompt_resets_the_turn(self) -> None:
        for _ in range(guard.MAX_TURN_BLOCKS + 1):
            guard.stop(self.payload("Done \N{EM DASH} all good.", active=True))
        guard.user_prompt_submit({"hook_event_name": "UserPromptSubmit", "session_id": "wall",
                                  "cwd": str(ROOT), "prompt": "next task"})
        response = guard.stop(self.payload("Done \N{EM DASH} all good.", active=True))
        self.assertEqual(response.get("decision"), "block")

    def test_the_order_matches_codex(self) -> None:
        calls: list[str] = []
        with (
            patch.object(guard, "run_unlazy_stop", lambda _: calls.append("unlazy") or {}),
            patch.object(guard, "method_evidence_violation",
                         lambda _: calls.append("evidence") or None),
            patch.object(guard, "clean_code_violation",
                         lambda _: calls.append("clean-code") or None),
            patch.object(guard, "unslop_violation",
                         lambda *_: calls.append("unslop") or None),
        ):
            guard.stop(self.payload("clean prose"))
        self.assertEqual(calls, ["unlazy", "evidence", "clean-code", "unslop"])


class SessionScopeTests(unittest.TestCase):
    """The code gate judges what this session wrote, not the whole diff."""

    def test_a_session_with_no_writes_has_nothing_to_judge(self) -> None:
        self.assertIsNone(rules.clean_code_violation(ROOT, []))

    def test_a_written_file_with_a_violation_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "bad.py").write_text("def f(a):\n    raise ValueError('x')\n",
                                         encoding="utf-8")
            reason = rules.clean_code_violation(root, ["bad.py"])
        self.assertIn("bad.py", reason)
        self.assertIn("what this session wrote", reason)


class RouteTokenTests(unittest.TestCase):
    def test_both_sigils_select_a_route(self) -> None:
        for text in ("$plan-flow", "/plan-flow", "please $plan-flow now"):
            with self.subTest(text=text):
                self.assertEqual(rules.route_from_prompt(text), "plan-flow")

    def test_the_last_route_named_wins(self) -> None:
        self.assertEqual(rules.route_from_prompt("$plan-flow then $implement-flow"),
                         "implement-flow")

    def test_an_unrelated_prompt_selects_nothing(self) -> None:
        self.assertIsNone(rules.route_from_prompt("please clean up the plan flow document"))

    def test_prompt_field_name_variants_are_both_read(self) -> None:
        self.assertEqual(guard.prompt_text({"prompt": "a"}), "a")
        self.assertEqual(guard.prompt_text({"prompt_text": "b"}), "b")


class PathScopeTests(unittest.TestCase):
    """Writes outside the repository are not this guard's business."""

    def test_a_path_outside_the_repository_is_dropped(self) -> None:
        self.assertIsNone(rules.normalized_path(ROOT, "/etc/passwd"))

    def test_a_path_inside_becomes_repository_relative(self) -> None:
        self.assertEqual(rules.normalized_path(ROOT, str(ROOT / "tools/x.py")), "tools/x.py")

    def test_the_scratchpad_and_the_home_directory_are_out_of_scope(self) -> None:
        outside = ["/tmp/scratch/plan.md", str(Path.home() / ".claude/plans/p.md")]
        self.assertEqual(rules.repository_paths(ROOT, outside), [])

    def test_bootstrap_paths_are_recognised(self) -> None:
        self.assertTrue(rules.bootstrap_only([".unlazy/demo/METHOD.json"]))
        self.assertTrue(rules.bootstrap_only([".unlazy/demo/GATES.md"]))
        self.assertFalse(rules.bootstrap_only([".unlazy/demo/METHOD.json", "tools/x.py"]))

    def test_the_ledger_is_always_writable(self) -> None:
        self.assertTrue(rules.always_writable(["MEMORY.md"]))

    def test_ownership_globs_match_their_directory(self) -> None:
        self.assertTrue(rules.owned("tools/x.py", ["tools/**"]))
        self.assertTrue(rules.owned("tools", ["tools/**"]))
        self.assertFalse(rules.owned("engine/x.py", ["tools/**"]))



class CommandGateTests(unittest.TestCase):
    """A shell command is a read or a change. The guard never guesses its paths.

    It used to parse commands for the files they write, and every heuristic
    produced a false denial on real work: a comparison inside a heredoc, an
    unexpanded variable, a relative path after a `cd`, a redirect character
    inside a quoted string. Ownership is checked on the tools that name a file.
    """

    def test_plain_reads_need_no_route(self) -> None:
        for command in ("git status", "ls -la", "cat README.md", "wc -l MEMORY.md",
                        "git diff HEAD", "rg pattern tools"):
            with self.subTest(command=command):
                self.assertEqual(rules.scan_command(command).kind, "none")

    def test_an_ambiguous_change_is_opaque(self) -> None:
        for command in ("python3 build.py", "npm install", "sed -i s/a/b/ f.py",
                        f"cat {chr(62)} tools/x.py"):
            with self.subTest(command=command):
                self.assertEqual(rules.scan_command(command).kind, "opaque")

    def test_an_unambiguous_mutation_names_its_paths(self) -> None:
        self.assertEqual(rules.scan_command("rm -rf engine").paths, ("engine",))
        self.assertEqual(rules.scan_command("mv tools/a.py engine/b.py").paths,
                         ("tools/a.py", "engine/b.py"))

    def test_a_mode_argument_is_not_a_path(self) -> None:
        self.assertEqual(rules.scan_command("chmod 777 tools/x.py").paths, ("tools/x.py",))

    def test_sed_reads_unless_it_edits_in_place(self) -> None:
        self.assertEqual(rules.scan_command("sed -n 1,5p f.py").kind, "none")
        self.assertEqual(rules.scan_command("sed -i s/a/b/ f.py").kind, "opaque")

    def test_a_read_with_a_shell_operator_is_not_trusted_as_a_read(self) -> None:
        self.assertEqual(rules.scan_command(f"cat a {chr(62)} b").kind, "opaque")

    def test_an_ambiguous_command_never_yields_a_path(self) -> None:
        commands = (f"cat {chr(62)} tools/x.py <<'PY'\nif a {chr(62)} b:\n pass\nPY",
                    f"cat {chr(62)} $SCRATCH/.token",
                    f"cd /elsewhere && cat {chr(62)} notes.md",
                    "printf '%s' 'x " + chr(62) + " denied'")
        for command in commands:
            with self.subTest(command=command[:30]):
                self.assertEqual(rules.scan_command(command).paths, ())


class AgentDocumentTests(unittest.TestCase):
    """writing-for-agents governs the documents, not only the briefs."""

    LAWFUL = {"standing_laws": ["unlazy", "writing-for-agents"], "owns": ["**"]}
    UNLAWFUL = {"standing_laws": ["unlazy"], "owns": ["**"]}

    def test_a_skill_body_needs_the_authoring_law(self) -> None:
        with self.assertRaises(ValueError) as caught:
            rules.require_writing_law([".agents/skills/x/SKILL.md"], self.UNLAWFUL)
        self.assertIn("writing-for-agents", str(caught.exception))

    def test_a_client_contract_needs_the_authoring_law(self) -> None:
        for name in ("AGENTS.md", "CLAUDE.md"):
            with self.subTest(document=name), self.assertRaises(ValueError):
                rules.require_writing_law([name], self.UNLAWFUL)

    def test_a_plan_document_needs_the_authoring_law(self) -> None:
        with self.assertRaises(ValueError):
            rules.require_writing_law(["design/some-plan.md"], self.UNLAWFUL)

    def test_a_source_file_does_not(self) -> None:
        rules.require_writing_law(["tools/x.py", "tests/test_x.py"], self.UNLAWFUL)

    def test_the_law_present_allows_the_write(self) -> None:
        rules.require_writing_law([".agents/skills/x/SKILL.md"], self.LAWFUL)


class BriefTests(unittest.TestCase):
    GOOD = ("You are a subagent. Don't run memo.\n"
            "Own: tools/x.py\n"
            "You are not alone in the codebase.\n"
            "Do not revert others' edits.\n"
            "Acceptance check: the named test passes and the diff touches only that file.\n")

    def test_a_complete_brief_passes(self) -> None:
        rules.validate_brief(self.GOOD, ROOT)

    def test_the_no_memo_sentence_must_appear_exactly_once(self) -> None:
        with self.assertRaises(ValueError):
            rules.validate_brief(self.GOOD + "You are a subagent. Don't run memo.\n", ROOT)

    def test_an_unslopped_brief_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            rules.validate_brief(self.GOOD + "Of course! delve in.\n", ROOT)
        self.assertIn("unslop", str(caught.exception))

    def test_a_brief_that_assumes_it_is_alone_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            rules.validate_brief(self.GOOD.replace(
                "You are not alone in the codebase.\n", ""), ROOT)
        self.assertIn("not alone", str(caught.exception))

    def test_a_brief_that_may_revert_other_agents_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            rules.validate_brief(self.GOOD.replace(
                "Do not revert others' edits.\n", ""), ROOT)
        self.assertIn("revert", str(caught.exception))

    def test_a_non_string_brief_names_what_arrived(self) -> None:
        with self.assertRaises(ValueError) as caught:
            rules.validate_brief(None, ROOT)
        self.assertIn("None", str(caught.exception))


class UnslopWallTests(unittest.TestCase):
    def test_the_wall_uses_the_repository_lint(self) -> None:
        violation = rules.unslop_violation("A reply \N{EM DASH} with a dash.", ROOT)
        self.assertIn("rule 13", violation)

    def test_clean_prose_passes_the_wall(self) -> None:
        self.assertIsNone(rules.unslop_violation("The guard denied the write.", ROOT))

    def test_an_empty_message_passes(self) -> None:
        self.assertIsNone(rules.unslop_violation("   ", ROOT))


if __name__ == "__main__":
    unittest.main(verbosity=1)
