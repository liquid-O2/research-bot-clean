from __future__ import annotations

import unittest

from tests.test_claude_method_guard import ROOT, rules


class AgentDocumentTests(unittest.TestCase):
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
