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

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
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
OBSOLETE_HOOKS = ("optmem_continuity.py",)
IMPORT_SMOKE = """import importlib.util, pathlib, sys
path = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location('claude_hook_import_smoke', path)
if spec is None or spec.loader is None:
    raise RuntimeError(f'cannot import {path}')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
"""


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
        "PostToolUse": group([hook(f"{GUARD} post-tool-use", 20)],
                             "Edit|Write|MultiEdit|NotebookEdit"),
        "SubagentStart": group([hook(f"{GUARD} subagent-start", 10)]),
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
    for name in OBSOLETE_HOOKS:
        obsolete = HOOKS / name
        if obsolete.is_file() or obsolete.is_symlink():
            obsolete.unlink()
    return sorted(installed)


def install_settings() -> int:
    """Write the tracked settings file and report its size."""
    body = json.dumps(settings_document(), indent=2) + "\n"
    SETTINGS.write_text(body, encoding="utf-8")
    return len(body)


def hook_file_pairs() -> list[tuple[Path, Path]]:
    pairs = [(TEMPLATES / name, HOOKS / name) for name in CLAUDE_HOOK_MODULES]
    pairs.append((TEMPLATES / CLAUDE_GUARD_TEMPLATE,
                  HOOKS / CLAUDE_GUARD_INSTALLED))
    return pairs


def import_error(path: Path) -> str | None:
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        (sys.executable, "-c", IMPORT_SMOKE, str(path)), cwd=ROOT,
        capture_output=True, text=True, timeout=10, check=False, env=environment,
    )
    if result.returncode == 0:
        return None
    detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "no stderr"
    return f"hook import failed for {path}: {detail}"


def hook_errors() -> list[str]:
    errors: list[str] = []
    for source, installed in hook_file_pairs():
        if not installed.is_file() or installed.read_bytes() != source.read_bytes():
            errors.append(f"installed Claude hook differs from template: {installed}")
    guard = HOOKS / CLAUDE_GUARD_INSTALLED
    if guard.is_file() and not guard.stat().st_mode & 0o111:
        errors.append(f"installed guard is not executable: {guard}")
    errors.extend(error for _, path in hook_file_pairs()
                  if path.is_file() and (error := import_error(path)))
    errors.extend(f"obsolete Claude hook remains: {HOOKS / name}"
                  for name in OBSOLETE_HOOKS if os.path.lexists(HOOKS / name))
    return errors


def settings_errors() -> list[str]:
    expected = (json.dumps(settings_document(), indent=2) + "\n").encode()
    if SETTINGS.is_file() and SETTINGS.read_bytes() == expected:
        return []
    return [f"installed Claude settings differ from generated settings: {SETTINGS}"]


def skill_link_errors() -> list[str]:
    try:
        names = install_claude_skills.expected_names(install_claude_skills.RECEIPT)
        actual = sorted(entry.name for entry in install_claude_skills.TARGET.iterdir())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"Claude skill links are unreadable: {error}"]
    errors = [] if actual == names else [f"Claude skill links are {actual!r}, expected {names!r}"]
    for name in names:
        link = install_claude_skills.TARGET / name
        if not link.is_symlink() or os.readlink(link) != install_claude_skills.link_target(name):
            errors.append(f"Claude skill link differs from authority: {link}")
    return errors


def current_errors() -> list[str]:
    return [*hook_errors(), *settings_errors(), *skill_link_errors()]


def install(stdout: TextIO) -> int:
    names = install_hooks()
    size = install_settings()
    install_claude_skills.main([], stdout)
    errors = current_errors()
    if errors:
        raise ValueError("\n".join(errors))
    stdout.write(f"CLAUDE HARNESS PASS hooks={len(names)} settings_bytes={size} "
                 f"events={len(settings_document()['hooks'])}\n")
    return 0


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout,
         stderr: TextIO = sys.stderr) -> int:
    """Install by default or run a read-only parity check. Example: ``main(["--check"])``."""
    parser = argparse.ArgumentParser(description="Install or check the Claude agent setup.")
    parser.add_argument("--check", action="store_true",
                        help="Check hooks, settings, and skill links without writing.")
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not arguments.check:
        return install(stdout)
    errors = current_errors()
    if errors:
        stderr.write("\n".join(errors) + "\n")
        return 1
    stdout.write("CLAUDE HARNESS CURRENT\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
