from __future__ import annotations

import sys
from pathlib import Path
import unittest


HOOKS = Path(__file__).resolve().parents[1] / "tools/harness_templates/hooks"
sys.path.insert(0, str(HOOKS))

from shell_reading import WriteScan, bare_engage, hidden_engage, scan_command  # noqa: E402


PROVEN_READS = (
    "python3 tools/memory_ledger.py tail 40",
    "/usr/bin/python3 tools/memory_ledger.py recall 'METHOD|HOOK'",
    "rg --files .agents/skills | rg principle | sort",
    "command -v method_guard.py",
    "find scratch -type f -print",
    "sed -n '1,80p' README.md",
    "git diff -- README.md",
    "sort README.md",
    "diff README.md START_HERE.md",
    "file README.md",
)

OPAQUE_COMMANDS = (
    "python3 -c 'open(\"out\", \"w\").write(\"x\")'",
    "python3 tools/memory_ledger.py checkpoint saved",
    "find scratch -delete",
    "find . -exec touch bypass {} +",
    "sed -n e touch bypass README.md",
    "sed --expression='e touch bypass' README.md",
    "rg --pre touch pattern .",
    "rg --pre=touch pattern .",
    "git diff --ext-diff",
    "sort -o out README.md",
    "sort --output=out README.md",
    "sort --compress-program=gzip README.md",
    "diff --output=out README.md START_HERE.md",
    "file --compile README.md",
    "git status\ntouch bypass",
    "rm tests/a;touch tests/b",
    "touch tests/a\nrm tests/b",
    "python3 tools/memory_ledger.py note fact>AGENTS.md",
    "rg pattern . | find scratch -delete",
    "rg pattern . > out",
)


class ShellReadingTests(unittest.TestCase):
    def test_proven_reads_need_no_method_route(self) -> None:
        for command in PROVEN_READS:
            with self.subTest(command=command):
                self.assertEqual(scan_command(command), WriteScan("none"))

    def test_execution_and_output_forms_stay_opaque(self) -> None:
        for command in OPAQUE_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(scan_command(command), WriteScan("opaque"))

    def test_memory_note_is_the_only_named_python_write(self) -> None:
        command = "python3 tools/memory_ledger.py note 'one lasting fact'"

        self.assertEqual(scan_command(command), WriteScan("paths", ("MEMORY.md",)))

    def test_engage_requires_one_plain_operator_free_command(self) -> None:
        plain = "python3 .codex/hooks/method_guard.py engage fixture"
        absolute = "/usr/bin/python3 /workspace/.codex/hooks/method_guard.py engage fixture"
        hidden = (
            f"{plain}; touch bypass",
            f"{plain}$(touch bypass)",
        )
        mentions = (
            "echo .codex/hooks/method_guard.py engage fixture",
            "python3 -c pass .codex/hooks/method_guard.py engage fixture",
            "/tmp/python3 .codex/hooks/method_guard.py engage fixture",
            "python3 /tmp/method_guard.py engage fixture",
            "python3 scratch/.codex/hooks/method_guard.py engage fixture",
        )

        self.assertTrue(bare_engage(plain))
        self.assertTrue(bare_engage(absolute))
        for command in hidden:
            with self.subTest(command=command):
                self.assertFalse(bare_engage(command))
                self.assertTrue(hidden_engage(command))
        for command in mentions:
            with self.subTest(command=command):
                self.assertFalse(bare_engage(command))
                self.assertFalse(hidden_engage(command))


if __name__ == "__main__":
    unittest.main()
