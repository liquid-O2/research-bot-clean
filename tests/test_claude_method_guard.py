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

    def test_stop_never_recurses(self) -> None:
        self.assertEqual(guard.stop({"stop_hook_active": True}), {})

    def test_subagent_stop_never_recurses(self) -> None:
        self.assertEqual(guard.subagent_stop({"stop_hook_active": True}), {})


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


class CommandTests(unittest.TestCase):
    def test_a_mutating_command_exposes_its_targets(self) -> None:
        self.assertEqual(rules.command_write_paths("rm -rf engine/x.py"), ["engine/x.py"])

    def test_a_redirect_exposes_its_target(self) -> None:
        self.assertIn("out.txt", rules.command_write_paths("echo hi > out.txt"))

    def test_an_in_place_sed_counts_as_a_write(self) -> None:
        self.assertIn("f.py", rules.command_write_paths("sed -i s/a/b/ f.py"))

    def test_a_plain_read_writes_nothing(self) -> None:
        self.assertIsNone(rules.command_write_paths("cat README.md"))

    def test_read_only_commands_are_recognised(self) -> None:
        for command in ("git status", "git diff HEAD", "ls -la", "wc -l MEMORY.md"):
            with self.subTest(command=command):
                self.assertTrue(rules.readonly_command(command))

    def test_a_piped_command_is_not_treated_as_read_only(self) -> None:
        self.assertFalse(rules.readonly_command("cat a > b"))


class HeredocTests(unittest.TestCase):
    """A heredoc body is data. Reading it as shell syntax denied a real write."""

    def command(self) -> str:
        operator = chr(62)
        return ("cat " + operator + " tools/target.py " + "<<'PY'\n"
                "if lines " + operator + " MAX_LINES:\n"
                "    raise ValueError(name)\n"
                "PY\n")

    def test_only_the_real_target_is_extracted(self) -> None:
        self.assertEqual(rules.command_write_paths(self.command()), ["tools/target.py"])

    def test_a_comparison_inside_a_heredoc_is_not_a_redirect(self) -> None:
        self.assertNotIn("MAX_LINES:", rules.command_write_paths(self.command()))

    def test_a_quoted_and_an_unquoted_marker_both_close(self) -> None:
        for marker in ("'PY'", "PY"):
            with self.subTest(marker=marker):
                body = f"cat {chr(62)} a.py <<{marker}\nx {chr(62)} y\nPY\n"
                self.assertEqual(rules.command_write_paths(body), ["a.py"])


class UnresolvablePathTests(unittest.TestCase):
    """A path the guard cannot resolve is opaque, not repository-relative."""

    def test_a_shell_variable_target_is_not_resolvable(self) -> None:
        self.assertFalse(rules.resolvable("$SCRATCH/.token"))

    def test_a_command_substitution_target_is_not_resolvable(self) -> None:
        self.assertFalse(rules.resolvable("$(mktemp)/file"))

    def test_a_literal_path_is_resolvable(self) -> None:
        self.assertTrue(rules.resolvable("tools/x.py"))
        self.assertTrue(rules.resolvable("/tmp/scratch/plan.md"))

    def test_a_home_relative_path_stays_resolvable(self) -> None:
        self.assertTrue(rules.resolvable("~/notes.md"))

    def test_a_variable_target_scans_as_opaque(self) -> None:
        command = "cat " + chr(62) + " $SCRATCH/.token"
        self.assertEqual(rules.scan_command(command).kind, "opaque")

    def test_a_literal_target_scans_as_paths(self) -> None:
        command = "cat " + chr(62) + " tools/x.py"
        self.assertEqual(rules.scan_command(command).kind, "paths")


class DirectoryChangeTests(unittest.TestCase):
    """A cd moves where relative paths land, and the payload cannot see that."""

    def command(self, target: str) -> str:
        return f"cd /elsewhere && cat {chr(62)} {target}"

    def test_a_relative_target_after_a_cd_is_opaque(self) -> None:
        self.assertEqual(rules.scan_command(self.command("notes.md")).kind, "opaque")

    def test_an_absolute_target_after_a_cd_still_resolves(self) -> None:
        scan = rules.scan_command(self.command("/tmp/notes.md"))
        self.assertEqual(scan.kind, "paths")
        self.assertIn("/tmp/notes.md", scan.paths)

    def test_a_relative_target_without_a_cd_still_resolves(self) -> None:
        self.assertEqual(rules.scan_command(f"cat {chr(62)} notes.md").kind, "paths")


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
