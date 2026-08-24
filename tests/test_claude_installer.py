from __future__ import annotations

from contextlib import ExitStack
from io import StringIO
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import install_agent_harness
import install_claude_harness


class ClaudeHarnessFixture:
    hook_modules = ("support.py",)
    guard_source = "guard.py"
    guard_installed = "claude_method_guard.py"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.templates = root / "templates"
        self.hooks = root / ".claude/hooks"
        self.settings = root / ".claude/settings.json"
        self.receipt = root / ".codex/harness/install-receipt.json"
        self.skills = root / ".claude/skills"
        self.stack = ExitStack()

    def __enter__(self) -> ClaudeHarnessFixture:
        self._patch_installer_paths()
        self._write_valid_installation()
        return self

    def __exit__(self, *error: object) -> None:
        self.stack.close()

    def _patch_installer_paths(self) -> None:
        values = {
            "ROOT": self.root,
            "TEMPLATES": self.templates,
            "HOOKS": self.hooks,
            "SETTINGS": self.settings,
            "CLAUDE_HOOK_MODULES": self.hook_modules,
            "CLAUDE_GUARD_TEMPLATE": self.guard_source,
            "CLAUDE_GUARD_INSTALLED": self.guard_installed,
            "GUARD": f"/usr/bin/python3 {self.hooks}/{self.guard_installed}",
            "MEMORY": f"/usr/bin/python3 {self.hooks}/memory_ledger_hooks.py",
        }
        for name, value in values.items():
            self.stack.enter_context(patch.object(install_claude_harness, name, value))
        skills = install_claude_harness.install_claude_skills
        self.stack.enter_context(patch.object(skills, "RECEIPT", self.receipt))
        self.stack.enter_context(patch.object(skills, "TARGET", self.skills))

    def _write_valid_installation(self) -> None:
        self.templates.mkdir(parents=True)
        self.hooks.mkdir(parents=True)
        for name, body in (("support.py", "VALUE = 1\n"), ("guard.py", "VALUE = 2\n")):
            (self.templates / name).write_text(body, encoding="utf-8")
        for source, installed in install_claude_harness.hook_file_pairs():
            installed.write_bytes(source.read_bytes())
        (self.hooks / self.guard_installed).chmod(0o755)
        body = json.dumps(install_claude_harness.settings_document(), indent=2) + "\n"
        self.settings.write_text(body, encoding="utf-8")
        self.receipt.parent.mkdir(parents=True)
        self.receipt.write_text('{"active_skill_names":["demo"]}\n', encoding="utf-8")
        self.skills.mkdir(parents=True)
        (self.skills / "demo").symlink_to("../../.agents/skills/demo")


def installed_tree_state(root: Path) -> dict[str, tuple[object, ...]]:
    state: dict[str, tuple[object, ...]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = ("link", os.readlink(path))
        elif path.is_file():
            state[relative] = ("file", path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
    return state


class ClaudeInstallerFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = ClaudeHarnessFixture(Path(self.temporary.name))
        self.fixture.__enter__()

    def tearDown(self) -> None:
        self.fixture.__exit__(None, None, None)
        self.temporary.cleanup()

    def test_missing_hook_reports_the_installed_path(self) -> None:
        missing = self.fixture.hooks / "support.py"
        missing.unlink()

        errors = install_claude_harness.hook_errors()

        self.assertEqual(errors, [f"installed Claude hook differs from template: {missing}"])

    def test_drifted_hook_reports_the_installed_path(self) -> None:
        drifted = self.fixture.hooks / "support.py"
        drifted.write_text("VALUE = 9\n", encoding="utf-8")

        errors = install_claude_harness.hook_errors()

        self.assertEqual(errors, [f"installed Claude hook differs from template: {drifted}"])

    def test_real_import_failure_reports_the_python_error(self) -> None:
        source = self.fixture.templates / "support.py"
        installed = self.fixture.hooks / "support.py"
        source.write_text("def broken(:\n", encoding="utf-8")
        installed.write_bytes(source.read_bytes())

        errors = install_claude_harness.hook_errors()

        self.assertEqual(len(errors), 1)
        self.assertIn(f"hook import failed for {installed}", errors[0])
        self.assertIn("SyntaxError: invalid syntax", errors[0])

    def test_settings_drift_reports_the_settings_path(self) -> None:
        self.fixture.settings.write_text("{}\n", encoding="utf-8")

        errors = install_claude_harness.settings_errors()

        self.assertEqual(errors, [
            f"installed Claude settings differ from generated settings: {self.fixture.settings}"
        ])

    def test_bad_skill_link_reports_the_link_path(self) -> None:
        link = self.fixture.skills / "demo"
        link.unlink()
        link.symlink_to("../wrong")

        errors = install_claude_harness.skill_link_errors()

        self.assertEqual(errors, [f"Claude skill link differs from authority: {link}"])

    def test_check_returns_nonzero_for_a_real_hook_mismatch(self) -> None:
        drifted = self.fixture.hooks / "support.py"
        drifted.write_text("VALUE = 9\n", encoding="utf-8")
        stdout = StringIO()
        stderr = StringIO()

        status = install_claude_harness.main(["--check"], stdout, stderr)

        self.assertEqual(status, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(f"installed Claude hook differs from template: {drifted}",
                      stderr.getvalue())

    def test_check_leaves_the_installed_tree_unchanged(self) -> None:
        before = installed_tree_state(self.fixture.root)
        stdout = StringIO()
        stderr = StringIO()

        status = install_claude_harness.main(["--check"], stdout, stderr)

        self.assertEqual(status, 0, stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "CLAUDE HARNESS CURRENT\n")
        self.assertEqual(installed_tree_state(self.fixture.root), before)


class ClaudeInstallerTests(unittest.TestCase):
    def test_hook_manifest_includes_every_transitive_runtime_module(self) -> None:
        names = set(install_claude_harness.CLAUDE_HOOK_MODULES)

        self.assertIn("shell_reading.py", names)
        self.assertIn("transcript_archive.py", names)

    def test_check_mode_never_calls_an_installer(self) -> None:
        output = StringIO()
        with (
            patch.object(install_claude_harness, "current_errors", return_value=[]),
            patch.object(install_claude_harness, "install_hooks",
                         side_effect=AssertionError("check mode installed hooks")),
            patch.object(install_claude_harness, "install_settings",
                         side_effect=AssertionError("check mode wrote settings")),
            patch.object(install_claude_harness.install_claude_skills, "main",
                         side_effect=AssertionError("check mode rewrote skill links")),
        ):
            status = install_claude_harness.main(["--check"], output)

        self.assertEqual(status, 0)

    def test_settings_deliver_child_context_and_keep_one_child_stop_owner(self) -> None:
        hooks = install_claude_harness.settings_document()["hooks"]

        self.assertIn("SubagentStart", hooks)
        start_commands = str(hooks["SubagentStart"])
        stop_commands = str(hooks["SubagentStop"])
        self.assertIn("method_guard.py subagent-start", start_commands)
        self.assertEqual(stop_commands.count("method_guard.py subagent-stop"), 1)
        self.assertNotIn("memory_ledger_hooks.py subagent-stop", stop_commands)

    def test_canonical_claude_skill_links_are_not_rejected(self) -> None:
        active = install_agent_harness.WORKSPACE / ".agents/skills"
        names = sorted(entry.name for entry in active.iterdir())

        errors = install_agent_harness.skill_tree_errors({"active_skill_names": names})

        self.assertFalse([error for error in errors if ".claude/skills" in error], errors)

    def test_codex_installer_does_not_manage_the_retired_claude_bridge(self) -> None:
        installed = [str(target) for _, target in install_agent_harness.managed_file_pairs()]

        self.assertFalse([path for path in installed if path.endswith("optmem_continuity.py")])


if __name__ == "__main__":
    unittest.main()
