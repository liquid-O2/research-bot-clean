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
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

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


if __name__ == "__main__":
    unittest.main(verbosity=1)
