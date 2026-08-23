#!/usr/bin/env python3
"""Install the Claude Code half of the method harness, and prove it landed.

Three parts, one command. The hook modules come from the same templates Codex
installs from, so neither client can drift. The settings file is tracked, so the
wiring is reviewable. The skills are symlinks into `.agents/skills`, so there is
one skill body on disk.

Re-running converges. Nothing here is destructive beyond overwriting the files
this installer owns.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from typing import Sequence, TextIO

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from agent_harness_verify_common import (  # noqa: E402
    CLAUDE_GUARD_INSTALLED,
    CLAUDE_GUARD_TEMPLATE,
    CLAUDE_HOOK_MODULES,
    ROOT,
)
import install_claude_skills  # noqa: E402

TEMPLATES = TOOLS / "harness_templates/hooks"
HOOKS = ROOT / ".claude/hooks"
SETTINGS = ROOT / ".claude/settings.json"
GUARD = f"/usr/bin/python3 {HOOKS}/{CLAUDE_GUARD_INSTALLED}"
MEMORY = f"/usr/bin/python3 {HOOKS}/memory_ledger_hooks.py"
WRITE_TOOLS = "Edit|Write|MultiEdit|NotebookEdit|Bash|Agent|Task"


def hook(command: str, timeout: int = 15) -> dict[str, object]:
    """Describe one hook command."""
    return {"type": "command", "command": command, "timeout": timeout}


def group(commands: Sequence[dict[str, object]], matcher: str = "") -> list[dict[str, object]]:
    """Describe one hook group, with an optional matcher."""
    entry: dict[str, object] = {"hooks": list(commands)}
    if matcher:
        entry["matcher"] = matcher
    return [entry]


def settings_document() -> dict[str, object]:
    """Return the tracked hook wiring for Claude Code."""
    return {"hooks": {
        "SessionStart": group([hook(f"{MEMORY} session-start", 20),
                               hook(f"{GUARD} session-start", 10)],
                              "startup|resume|clear|compact"),
        "UserPromptSubmit": group([hook(f"{GUARD} user-prompt-submit", 10)]),
        "PreToolUse": group([hook(f"{GUARD} pre-tool-use", 20)], WRITE_TOOLS),
        "SubagentStop": group([hook(f"{GUARD} subagent-stop", 15)]),
        "Stop": group([hook(f"{GUARD} stop", 30)]),
        "PreCompact": group([hook(f"{MEMORY} pre-compact", 30)], "manual|auto"),
        "SessionEnd": group([hook(f"{MEMORY} session-end", 10)]),
    }}


def install_hooks() -> list[str]:
    """Copy every Claude hook module from the shared templates."""
    HOOKS.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for name in CLAUDE_HOOK_MODULES:
        shutil.copy2(TEMPLATES / name, HOOKS / name)
        installed.append(name)
    guard = HOOKS / CLAUDE_GUARD_INSTALLED
    shutil.copy2(TEMPLATES / CLAUDE_GUARD_TEMPLATE, guard)
    guard.chmod(0o755)
    installed.append(CLAUDE_GUARD_INSTALLED)
    return sorted(installed)


def install_settings() -> int:
    """Write the tracked settings file and report its size."""
    body = json.dumps(settings_document(), indent=2) + "\n"
    SETTINGS.write_text(body, encoding="utf-8")
    return len(body)


def verify_installed(names: Sequence[str]) -> None:
    """Check every module landed and the guard is executable."""
    for name in names:
        path = HOOKS / name
        if not path.is_file():
            raise ValueError(f"hook module did not install: {path}")
    guard = HOOKS / CLAUDE_GUARD_INSTALLED
    if not guard.stat().st_mode & 0o111:
        raise ValueError(f"installed guard is not executable: {guard}")


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Install hooks, settings and skills, then report what landed."""
    names = install_hooks()
    verify_installed(names)
    size = install_settings()
    install_claude_skills.main([], stdout)
    stdout.write(f"CLAUDE HARNESS PASS hooks={len(names)} settings_bytes={size} "
                 f"events={len(settings_document()['hooks'])}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
