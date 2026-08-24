#!/usr/bin/env python3
"""Check a subagent brief before it is dispatched.

Thin by design. The rules live in the guard's shared rules module, which is what
the PreToolUse hook enforces, so a brief that passes here passes there and there
is one place to change a rule.

Read a brief on stdin, or name a file. A clean brief exits zero.
"""

from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Iterator, Sequence, TextIO

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / ".claude/hooks/method_guard_rules.py"
TEMPLATE_RULES = ROOT / "tools/harness_templates/hooks/method_guard_rules.py"
CHECKLIST = (
    "The exact sentence `You are a subagent. Don't run memo.`, once.",
    "Explicit file ownership on its own line, starting with Own or Ownership.",
    "An `Acceptance check:` with a bound the worker can decide.",
    "A line saying the worker is not alone in the codebase.",
    "A line saying not to revert other agents' edits.",
    "Prose that passes the unslop lint.",
)
HOOK_IMPORTS = ("shell_reading", "method_guard_support")


@contextmanager
def isolated_hook_imports(directory: Path) -> Iterator[None]:
    saved = {name: sys.modules.pop(name) for name in HOOK_IMPORTS if name in sys.modules}
    sys.path.insert(0, str(directory))
    try:
        yield
    finally:
        sys.path.pop(0)
        for name in HOOK_IMPORTS:
            sys.modules.pop(name, None)
        sys.modules.update(saved)


def load_rules(path: Path) -> ModuleType:
    """Import the guard's rules module, installed copy first."""
    source = path if path.is_file() else TEMPLATE_RULES
    spec = importlib.util.spec_from_file_location("brief_lint_rules", source)
    if spec is None or spec.loader is None:
        raise ValueError(f"guard rules module could not be loaded from {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["brief_lint_rules"] = module
    with isolated_hook_imports(source.parent):
        spec.loader.exec_module(module)
    return module


def read_brief(arguments: Sequence[str], stdin: TextIO) -> str:
    """Return the brief text from a named file or from stdin."""
    if not arguments or arguments[0] == "-":
        return stdin.read()
    return Path(arguments[0]).read_text(encoding="utf-8")


def report_checklist(stdout: TextIO) -> None:
    """Print what a brief must carry, so the fix is obvious."""
    stdout.write("A brief must carry:\n")
    stdout.writelines(f"  - {item}\n" for item in CHECKLIST)


def main(argv: Sequence[str] | None = None, stdin: TextIO = sys.stdin,
         stdout: TextIO = sys.stdout) -> int:
    """Check one brief and report the first rule it breaks."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    rules = load_rules(RULES)
    try:
        rules.validate_brief(read_brief(arguments, stdin), ROOT)
    except ValueError as error:
        stdout.write(f"BRIEF FAIL {error}\n\n")
        report_checklist(stdout)
        return 1
    stdout.write("BRIEF PASS\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
