from __future__ import annotations

import sys
from pathlib import Path
import unittest


HOOKS = Path(__file__).resolve().parents[1] / "tools/harness_templates/hooks"
sys.path.insert(0, str(HOOKS))

from shell_reading import WriteScan, scan_command  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
