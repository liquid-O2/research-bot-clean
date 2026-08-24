#!/usr/bin/env python3
"""Prove the Claude guard reads real payloads and fails open on its own bugs.

Behaviour end to end is covered by `tools/run_method_canaries.py`, which drives
the installed hook the way the client drives it. This suite covers what canaries
cannot: that the extraction matches payloads captured from live hook runs, and
that an unexpected internal failure lets the call through instead of denying it.
"""

from __future__ import annotations

from io import StringIO
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
from contextlib import contextmanager
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude/hooks"
FIXTURES = ROOT / "tests/fixtures/claude_hook_payloads"
HOOK_SIBLINGS = ("method_guard_support", "method_guard_rules", "shell_reading",
                 "transcript_archive")


@contextmanager
def isolated_hook_imports(directory: Path) -> Iterator[None]:
    """Keep one client family's generic hook imports out of other suites."""
    saved = {name: sys.modules.pop(name) for name in HOOK_SIBLINGS if name in sys.modules}
    original_path = list(sys.path)
    sys.path.insert(0, str(directory))
    try:
        yield
    finally:
        for name in HOOK_SIBLINGS:
            sys.modules.pop(name, None)
        sys.modules.update(saved)
        sys.path[:] = original_path


def load(name: str, path: Path) -> ModuleType | None:
    """Import one installed hook module by path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    with isolated_hook_imports(path.parent):
        spec.loader.exec_module(module)
    return module


guard = load("claude_guard_under_test", HOOKS / "method_guard.py")
rules = guard.rules


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

    def test_subagent_start_is_an_active_guard_event(self) -> None:
        self.assertIn("subagent-start", guard.EVENTS)

    def test_compact_delegates_to_exact_packet_restoration(self) -> None:
        expected = {"systemMessage": "restored exact packet"}
        payload = {"hook_event_name": "SessionStart", "session_id": "session-fixture",
                   "cwd": str(ROOT), "source": "compact"}
        with patch.object(guard.policy, "session_start", return_value=expected) as restore:
            response = guard.session_start(payload)

        self.assertEqual(response, expected)
        restore.assert_called_once_with(payload)

    def test_subagent_start_delegates_to_exact_packet_delivery(self) -> None:
        expected = {"systemMessage": "delivered exact packet"}
        payload = fixture("SubagentStart")
        self.assertTrue(hasattr(guard, "subagent_start"))
        with patch.object(guard.policy, "subagent_start", return_value=expected) as deliver:
            response = guard.subagent_start(payload)

        self.assertEqual(response, expected)
        deliver.assert_called_once_with(payload)


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

    def test_engage_writes_the_packet_text_and_marks_the_final_chunk_ready(self) -> None:
        packet = guard.policy.ExactMethodPacket("exact packet", "a" * 64, 12, {})
        state = {"pending_ready": {"scope": "fixture"}}
        output = StringIO()
        errors = StringIO()
        with (
            patch.object(guard, "direct_payload",
                         return_value={"cwd": str(ROOT), "session_id": "session-fixture"}),
            patch.object(guard.policy, "prepare_engagement", return_value=(packet, state)),
            patch.object(guard.policy, "rearm"),
            patch.object(guard.policy, "mark_ready") as mark_ready,
        ):
            try:
                status = guard.run_engage(["engage", "fixture"], output, errors)
            except TypeError as error:
                self.fail(f"engage serialized its packet object: {error}")

        self.assertEqual(status, 0)
        self.assertIn("exact packet", output.getvalue())
        self.assertIn("<<<METHOD_PACKET_CHUNK_END>>>", output.getvalue())
        mark_ready.assert_called_once()


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

    def test_child_blocks_do_not_release_the_parent_stop_wall(self) -> None:
        child = self.payload("Done \N{EM DASH} all good.", active=True)
        child["hook_event_name"] = "SubagentStop"
        child["agent_id"] = "child-fixture"
        for _ in range(guard.MAX_TURN_BLOCKS):
            guard.subagent_stop(child)
        with (
            patch.object(guard, "run_unlazy_stop", return_value={}),
            patch.object(guard, "method_evidence_violation", return_value=None),
            patch.object(guard, "clean_code_violation", return_value=None),
        ):
            response = guard.stop(self.payload("Done \N{EM DASH} all good.", active=True))

        self.assertEqual(response.get("decision"), "block")

    def test_unlazy_receives_only_the_scope_bound_to_this_session(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            scope = root / ".unlazy/active"
            scope.mkdir(parents=True)
            (scope / "session").write_text("wall\n", encoding="utf-8")
            payload = self.payload("clean prose")
            state = {"scope": "active", "route": "implement-flow"}
            with (
                patch.object(guard.policy, "repo_root", return_value=root),
                patch.object(guard.policy, "load_state", return_value=state),
                patch.object(guard.rules, "run_unlazy_stop", return_value={}) as run,
            ):
                guard.run_unlazy_stop(payload)

        run.assert_called_once_with(payload, root, "active")

    def test_an_accepted_child_stop_archives_its_final_transcript(self) -> None:
        payload = dict(fixture("SubagentStop"))
        payload["last_assistant_message"] = "The acceptance check passed."
        with patch.object(guard, "archive_transcript", create=True) as archive:
            response = guard.subagent_stop(payload)

        self.assertEqual(response, {})
        archive.assert_called_once_with(payload["agent_transcript_path"])

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

    def test_an_unrelated_method_scope_edit_does_not_rearm_the_active_scope(self) -> None:
        state = {"scope": "active", "ready": {"packet": "current"}}
        payload = {"session_id": "scope-fixture", "cwd": str(ROOT)}
        with patch.object(guard.policy, "rearm") as rearm:
            guard.rearm_on_contract_edit([".unlazy/unrelated/GATES.md"], state, payload)

        rearm.assert_not_called()



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

    def test_commands_with_write_capable_read_flags_are_not_reads(self) -> None:
        commands = ("find . -delete", "git branch -D old",
                    "sed -n 'w output.txt' input.txt", "rg --pre sh pattern")
        for command in commands:
            with self.subTest(command=command):
                self.assertNotEqual(rules.scan_command(command).kind, "none")


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


class ReceiptDigestTests(unittest.TestCase):
    """The review wall must see every uncommitted change, new files included."""

    def repo(self, root: Path) -> None:
        import subprocess
        subprocess.run(("git", "init", "-q", str(root)), check=True)
        (root / "tracked.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(root), "add", "-A"), check=True)
        subprocess.run(("git", "-C", str(root), "-c", "user.name=t",
                        "-c", "user.email=t@t", "commit", "-q", "-m", "base"), check=True)

    def test_a_clean_tree_has_no_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.repo(root)
            self.assertIsNone(rules.diff_digest(root))

    def test_an_edit_to_a_tracked_file_changes_the_digest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.repo(root)
            (root / "tracked.py").write_text("x = 2\n", encoding="utf-8")
            self.assertIsNotNone(rules.diff_digest(root))

    def test_a_brand_new_file_changes_the_digest(self) -> None:
        """git diff HEAD alone is blind to this, and the wall was too."""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.repo(root)
            (root / "created.py").write_text("y = 1\n", encoding="utf-8")
            self.assertIsNotNone(rules.diff_digest(root))

    def test_new_file_content_matters_not_just_its_name(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.repo(root)
            (root / "created.py").write_text("y = 1\n", encoding="utf-8")
            first = rules.diff_digest(root)
            (root / "created.py").write_text("y = 2\n", encoding="utf-8")
            self.assertNotEqual(first, rules.diff_digest(root))


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
