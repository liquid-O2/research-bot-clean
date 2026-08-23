#!/usr/bin/env python3
"""Install this agent method into a repository.

Lays down the skills, the pinned upstream sources, both clients' hooks, the
contract and the tooling, then tells you how to prove it works.

Nothing here is destructive beyond the paths it owns. Re-running converges.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
from typing import Sequence, TextIO

HERE = Path(__file__).resolve().parent
CLAUDE_HOOKS = ("method_guard_support.py", "method_guard_rules.py", "memory_ledger_hooks.py")
CODEX_HOOKS = ("method_guard.py", "method_guard_support.py", "method_guard_rules.py",
               "optmem_lifecycle.py")
TOOL_NAMES = ("unslop_lint.py", "unslop_rules.py", "unslop_allowlist.txt",
              "clean_code_lint.py", "brief_lint.py", "memory_ledger.py",
              "install_claude_skills.py", "run_method_canaries.py")


def copy_dir(source: Path, destination: Path) -> int:
    """Copy a directory, reporting how many files landed."""
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return sum(1 for path in destination.rglob("*") if path.is_file())


def copy_files(names: Sequence[str], source: Path, destination: Path) -> int:
    """Copy named files into one directory."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(source / name, destination / name)
    return len(names)


def link_skills(target: Path) -> int:
    """Point Claude Code at the canonical skills without copying a body."""
    authority = target / ".agents/skills"
    mirror = target / ".claude/skills"
    mirror.mkdir(parents=True, exist_ok=True)
    linked = 0
    for entry in sorted(authority.iterdir()):
        link = mirror / entry.name
        if link.is_symlink():
            link.unlink()
        link.symlink_to(f"../../.agents/skills/{entry.name}")
        linked += 1
    return linked


def install_skills(target: Path) -> int:
    """Copy the canonical skill bodies and the pinned upstream sources."""
    copied = copy_dir(HERE / "skills", target / ".agents/skills")
    return copied + copy_dir(HERE / "vendor", target / "vendor/agent-sources")


def write_settings(target: Path) -> int:
    """Write the hook wiring with every path pointing at this repository."""
    body = (HERE / "claude/settings.json").read_text(encoding="utf-8")
    destination = target / ".claude/settings.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(body.replace("__REPO__", str(target)), encoding="utf-8")
    return 1


def install_hooks(target: Path) -> int:
    """Install both clients' hook modules and their wiring."""
    hooks = HERE / "hooks"
    copied = copy_files(CLAUDE_HOOKS, hooks, target / ".claude/hooks")
    shutil.copy2(hooks / "claude_method_guard.py", target / ".claude/hooks/method_guard.py")
    (target / ".claude/hooks/method_guard.py").chmod(0o755)
    copied += copy_files(CODEX_HOOKS, hooks, target / ".codex/hooks") + 1
    copied += write_settings(target)
    copied += copy_files(("method-worker.md",), HERE / "claude/agents", target / ".claude/agents")
    copied += copy_files(("hooks.json",), HERE / "codex", target / ".codex")
    return copied


def install_tools(target: Path) -> int:
    """Install the lints, the ledger and the canary runner."""
    return copy_files(TOOL_NAMES, HERE / "tools", target / "tools")


def install_contract(target: Path) -> int:
    """Install the shared contract for both clients."""
    return copy_files(("AGENTS.md", "CLAUDE.md"), HERE / "contract", target)


def next_steps(target: Path) -> str:
    """Return what to run to prove the install."""
    return (f"""
Installed into {target}. Prove it:

    cd {target}
    python3 tools/unslop_lint.py AGENTS.md CLAUDE.md
    python3 tools/clean_code_lint.py .claude/hooks
    python3 tools/run_method_canaries.py --client claude

Then start a session and type $implement-flow. The guard will tell you what to
write next and refuse a repository write until its method is in context.

The hook command paths in .claude/settings.json already point at this
repository. Codex reads .codex/hooks.json, whose paths you set yourself.
""")


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Install the harness into the named repository."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        raise ValueError(f"usage: install.py <target-repository>, got {arguments!r}")
    target = Path(arguments[0]).resolve()
    counts = {"skills": install_skills(target), "hooks": install_hooks(target),
              "tools": install_tools(target), "contract": install_contract(target)}
    counts["links"] = link_skills(target)
    stdout.write("INSTALL PASS " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    stdout.write(next_steps(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
