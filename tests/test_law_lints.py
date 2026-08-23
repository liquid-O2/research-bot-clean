#!/usr/bin/env python3
"""Prove the unslop lint decides the rules it claims to decide.

The lint is the enforcement point for a mandatory law, so a rule that silently
stops firing is a law that silently stops applying. Every encoded rule gets a
line that must trip it, and every exemption gets a line that must not.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import brief_lint  # noqa: E402
import clean_code_lint  # noqa: E402
import unslop_lint  # noqa: E402

DIRTY = {
    7: "This release is a testament to the work.",
    8: "The module serves as the entry point.",
    9: "It is not just fast, but also correct.",
    13: "One clause \N{EM DASH} then another.",
    14: "If you are coming from the old runner: instead of handlers, you declare rules.",
    17: "# A Title Case Heading Here",
    18: "- \N{PARTY POPPER} shipped the thing",
    19: "He said “hello” loudly.",
    20: "Of course! Here is the file.",
    22: "You're absolutely right about that.",
    23: "In order to run it, call the script.",
    26: "The substrate underneath is stable.",
}
CLEAN = """# Sentence case heading

The guard denies a write when the method packet has not entered the session.
It records the source hashes and re-arms after a compaction.

- The hook returns a reason that names the fix.
- A denied write leaves the file unchanged.
"""


def findings(text: str) -> list[unslop_lint.Finding]:
    """Lint one snippet with the repository allowlist."""
    return unslop_lint.lint_text(text, "<test>", unslop_lint.read_allowlist())


def rules(text: str) -> set[int]:
    """Return the rule numbers a snippet trips."""
    return {finding.rule for finding in findings(text)}


class UnslopRuleTests(unittest.TestCase):
    def test_every_encoded_rule_fires_on_its_own_dirty_line(self) -> None:
        for number, line in DIRTY.items():
            with self.subTest(rule=number):
                self.assertIn(number, rules(line))

    def test_clean_prose_trips_nothing(self) -> None:
        self.assertEqual(findings(CLEAN), [])

    def test_a_finding_names_its_rule_and_span(self) -> None:
        found = findings(DIRTY[13])[0]
        self.assertEqual(found.rule, 13)
        self.assertEqual(found.span, "\N{EM DASH}")
        self.assertEqual(found.line, 1)


class UnslopExemptionTests(unittest.TestCase):
    def test_a_verbatim_upstream_block_is_exempt(self) -> None:
        text = ("<!-- AKITA_UPSTREAM_BLOCK_BEGIN -->\n"
                f"{DIRTY[13]}\n"
                "<!-- AKITA_UPSTREAM_BLOCK_END -->\n")
        self.assertEqual(findings(text), [])

    def test_an_explicit_ignore_region_is_exempt(self) -> None:
        text = f"<!-- unslop:ignore-start -->\n{DIRTY[7]}\n<!-- unslop:ignore-end -->\n"
        self.assertEqual(findings(text), [])

    def test_text_after_an_ignore_region_is_scanned_again(self) -> None:
        text = ("<!-- unslop:ignore-start -->\n"
                f"{DIRTY[7]}\n"
                "<!-- unslop:ignore-end -->\n"
                f"{DIRTY[13]}\n")
        self.assertEqual(rules(text), {13})

    def test_fenced_code_is_exempt(self) -> None:
        self.assertEqual(findings(f"```\n{DIRTY[13]}\n```\n"), [])

    def test_frontmatter_is_exempt(self) -> None:
        self.assertEqual(findings(f"---\nname: x \N{EM DASH} y\n---\nplain line\n"), [])

    def test_an_inline_code_span_is_exempt(self) -> None:
        self.assertEqual(findings("Run `a --b \N{EM DASH} c` now.\n"), [])

    def test_the_allowlist_suppresses_a_term_used_concretely(self) -> None:
        self.assertNotIn(26, rules("The agent harness installs the hooks."))


class ColonHeuristicTests(unittest.TestCase):
    def test_a_short_label_colon_is_allowed(self) -> None:
        self.assertNotIn(14, rules("Note: the tool manages this file."))

    def test_a_colon_before_a_list_is_allowed(self) -> None:
        self.assertNotIn(14, rules("The guard checks three things:\n"))

    def test_a_label_after_a_numbered_marker_is_allowed(self) -> None:
        line = ("The rule is long and says several things first. (2) ENGAGEMENT: before the "
                "first write the guard injects the sources.")
        self.assertNotIn(14, rules(line))

    def test_a_label_after_a_sentence_boundary_is_allowed(self) -> None:
        line = "This sentence runs on for a while and then ends. Note: the tool manages it."
        self.assertNotIn(14, rules(line))

    def test_a_connector_deep_in_a_line_is_still_caught(self) -> None:
        line = ("An unrelated opening sentence sits here. If you are coming from the old "
                "runner: instead of handlers, you declare rules.")
        self.assertIn(14, rules(line))

    def test_a_time_and_a_url_are_allowed(self) -> None:
        self.assertNotIn(14, rules("The run started at 09:30 and finished later on."))


class RealContractTests(unittest.TestCase):
    def test_the_shipped_contract_passes_its_own_lint(self) -> None:
        allowlist = unslop_lint.read_allowlist()
        for name in ("AGENTS.md",):
            with self.subTest(document=name):
                self.assertEqual(unslop_lint.lint_path(ROOT / name, allowlist), [])


class CommandLineTests(unittest.TestCase):
    def test_stdin_reports_findings_and_exits_nonzero(self) -> None:
        output = StringIO()
        status = unslop_lint.main(["-"], StringIO(DIRTY[13]), output)
        self.assertEqual(status, 1)
        self.assertIn("rule=13", output.getvalue())

    def test_clean_stdin_exits_zero(self) -> None:
        output = StringIO()
        self.assertEqual(unslop_lint.main(["-"], StringIO(CLEAN), output), 0)

    def test_json_output_is_machine_readable(self) -> None:
        output = StringIO()
        unslop_lint.main(["--json", "-"], StringIO(DIRTY[20]), output)
        rows = json.loads(output.getvalue())
        self.assertEqual(rows[0]["rule"], 20)
        self.assertIn("message", rows[0])


Q3 = chr(34) * 3
DIRTY_CODE = {
    "function-too-long": "def f(a: int) -> int:\n" + "    a += 1\n" * 25 + "    return a\n",
    "nesting-too-deep": ("def f(a: int) -> int:\n    if a:\n        for _ in range(a):\n"
                         "            while a:\n                a -= 1\n    return a\n"),
    "missing-parameter-type": "def f(a) -> int:\n    return 1\n",
    "missing-return-type": "def f(a: int):\n    return 1\n",
    "vague-type": "from typing import Any\ndef f(a: Any) -> int:\n    return 1\n",
    "opaque-exception": 'def f(a: int) -> int:\n    raise ValueError("bad")\n',
}
CLEAN_CODE = (
    "def add(left: int, right: int) -> int:\n"
    f"    {Q3}Return the sum, naming the value when it is not a number.{Q3}\n"
    "    if not isinstance(left, int):\n"
    '        raise TypeError(f"left must be an int, got {left!r}")\n'
    "    return left + right\n"
)
GOOD_BRIEF = ("You are a subagent. Don't run memo.\n"
              "Own: tools/x.py\n"
              "You are not alone in the codebase.\n"
              "Do not revert others' edits.\n"
              "Acceptance check: the named test passes.\n")


def code_rules(source: str) -> set[str]:
    """Return the clean-code rules one snippet trips."""
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "sample.py"
        path.write_text(source, encoding="utf-8")
        return {finding.rule for finding in clean_code_lint.lint_file(path)}


class CleanCodeRuleTests(unittest.TestCase):
    def test_every_encoded_rule_fires_on_its_own_dirty_snippet(self) -> None:
        for rule, source in DIRTY_CODE.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, code_rules(source))

    def test_clean_code_trips_nothing(self) -> None:
        self.assertEqual(code_rules(CLEAN_CODE), set())

    def test_control_flow_exceptions_are_not_opaque(self) -> None:
        source = "def f() -> int:\n    raise SystemExit(1)\n"
        self.assertNotIn("opaque-exception", code_rules(source))

    def test_a_long_file_is_flagged(self) -> None:
        source = "x = 1\n" * (clean_code_lint.MAX_FILE_LINES + 1)
        self.assertIn("file-too-long", code_rules(source))

    def test_the_shipped_harness_passes_its_own_rule(self) -> None:
        findings = [row for path in sorted((ROOT / ".claude/hooks").glob("*.py"))
                    for row in clean_code_lint.lint_file(path)]
        self.assertEqual([row.message for row in findings], [])


class BriefLintTests(unittest.TestCase):
    def test_a_complete_brief_passes(self) -> None:
        self.assertEqual(brief_lint.main(["-"], StringIO(GOOD_BRIEF), StringIO()), 0)

    def test_each_missing_element_is_reported(self) -> None:
        removals = ("You are a subagent. Don't run memo.\n", "Own: tools/x.py\n",
                    "You are not alone in the codebase.\n", "Do not revert others' edits.\n",
                    "Acceptance check: the named test passes.\n")
        for line in removals:
            with self.subTest(missing=line.strip()):
                output = StringIO()
                status = brief_lint.main(["-"], StringIO(GOOD_BRIEF.replace(line, "")), output)
                self.assertEqual(status, 1)
                self.assertIn("BRIEF FAIL", output.getvalue())

    def test_an_unslopped_brief_is_reported(self) -> None:
        output = StringIO()
        brief = GOOD_BRIEF + "Of course! This is a testament to the work.\n"
        self.assertEqual(brief_lint.main(["-"], StringIO(brief), output), 1)
        self.assertIn("unslop", output.getvalue())

    def test_a_failure_prints_the_checklist(self) -> None:
        output = StringIO()
        brief_lint.main(["-"], StringIO("do it"), output)
        self.assertIn("A brief must carry", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=1)
