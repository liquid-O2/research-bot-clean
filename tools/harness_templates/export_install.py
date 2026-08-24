#!/usr/bin/env python3
"""Install or verify the exported agent method in one repository."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
import sys
from typing import Sequence, TextIO


HERE = Path(__file__).resolve().parent
CODEX_HOOK_MODULES = (
    "memory_ledger_hooks.py", "method_guard.py", "method_guard_rules.py",
    "method_guard_support.py", "shell_reading.py", "transcript_archive.py",
)
CLAUDE_HOOK_MODULES = CODEX_HOOK_MODULES
OBSOLETE_CODEX_HOOKS = ("cached_session_bridge.py", "optmem_lifecycle.py")
OBSOLETE_CLAUDE_HOOKS = ("optmem_continuity.py",)
REQUIRED_IGNORES = (".unlazy/", "MEMORY.md")
EMPTY_MEMORY_LEDGER = """# Memory

Durable project decisions and continuity checkpoints live here.

## Ledger

## Checkpoints
"""


def copy_file(source: Path, destination: Path) -> int:
    """Copy one managed file."""
    if not source.is_file():
        raise ValueError(f"install source {source} is missing; expected a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return 1


def copy_tree(source: Path, destination: Path) -> int:
    """Copy one managed tree and return its source file count."""
    if not source.is_dir():
        raise ValueError(f"install source {source} is missing; expected a directory")
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False)
    return sum(path.is_file() for path in source.rglob("*"))


def render_hooks_config(target: Path) -> bytes:
    """Resolve every portable hook command against the target repository."""
    template = (HERE / ".codex/hooks.json").read_text(encoding="utf-8")
    return template.replace("__REPO__", str(target)).encode()


def render_claude_settings(target: Path) -> bytes:
    """Resolve every portable Claude command against the target repository."""
    template = (HERE / ".claude/settings.json").read_text(encoding="utf-8")
    return template.replace("__REPO__", str(target)).encode()


def install_hooks(target: Path) -> int:
    """Install current Codex hook modules and remove obsolete owned modules."""
    source = HERE / "tools/harness_templates/hooks"
    destination = target / ".codex/hooks"
    copied = sum(copy_file(source / name, destination / name) for name in CODEX_HOOK_MODULES)
    for name in OBSOLETE_CODEX_HOOKS:
        obsolete = destination / name
        if obsolete.is_file() or obsolete.is_symlink():
            obsolete.unlink()
    config = target / ".codex/hooks.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_bytes(render_hooks_config(target))
    return copied + 1


def install_claude_hooks(target: Path) -> int:
    """Install Claude hooks, settings, worker, and canonical skill links."""
    source = HERE / ".claude/hooks"
    destination = target / ".claude/hooks"
    copied = sum(copy_file(source / name, destination / name) for name in CLAUDE_HOOK_MODULES)
    (destination / "method_guard.py").chmod(0o755)
    for name in OBSOLETE_CLAUDE_HOOKS:
        obsolete = destination / name
        if obsolete.is_file() or obsolete.is_symlink():
            obsolete.unlink()
    settings = target / ".claude/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_bytes(render_claude_settings(target))
    copied += copy_tree(HERE / ".claude/agents", target / ".claude/agents")
    return copied + 1 + install_claude_skill_links(target)


def install_claude_skill_links(target: Path) -> int:
    """Link Claude to the one canonical skill authority."""
    authority = target / ".agents/skills"
    links = target / ".claude/skills"
    links.mkdir(parents=True, exist_ok=True)
    names = sorted(entry.name for entry in authority.iterdir() if entry.is_dir())
    for entry in list(links.iterdir()):
        if entry.name not in names and entry.is_symlink():
            entry.unlink()
    for name in names:
        link = links / name
        wanted = Path("../../.agents/skills") / name
        if link.is_symlink() and link.readlink() == wanted:
            continue
        if link.exists() or link.is_symlink():
            raise ValueError(f"Claude skill path {link} is not the expected symlink")
        link.symlink_to(wanted)
    return len(names)


def install_gitignore(target: Path) -> int:
    """Add the private method state paths without changing existing rules."""
    path = target / ".gitignore"
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = current.splitlines()
    missing = [rule for rule in REQUIRED_IGNORES if rule not in lines]
    if missing:
        separator = "" if not current or current.endswith("\n") else "\n"
        path.write_text(current + separator + "\n".join(missing) + "\n", encoding="utf-8")
    return 1


def install_memory_ledger(target: Path) -> int:
    """Create the private ledger once without replacing repository history."""
    path = target / "MEMORY.md"
    if path.is_file():
        return 0
    if path.exists() or path.is_symlink():
        raise ValueError(f"memory ledger {path} is not a regular file")
    path.write_text(EMPTY_MEMORY_LEDGER, encoding="utf-8")
    path.chmod(0o600)
    return 1


def install(target: Path) -> dict[str, int]:
    """Copy every managed method component into the target."""
    if target == HERE:
        raise ValueError(f"install target {target} is the export bundle; expected another repository")
    target.mkdir(parents=True, exist_ok=True)
    counts = {
        "skills": copy_tree(HERE / ".agents/skills", target / ".agents/skills"),
    }
    counts.update({
        "claude": install_claude_hooks(target),
        "claude-contract": copy_file(HERE / "CLAUDE.md", target / "CLAUDE.md"),
        "contract": copy_file(HERE / "AGENTS.md", target / "AGENTS.md"),
        "gitignore": install_gitignore(target),
        "hooks": install_hooks(target),
        "memory": install_memory_ledger(target),
        "sources": copy_tree(HERE / "vendor/agent-sources", target / "vendor/agent-sources"),
        "tests": copy_tree(HERE / "tests", target / "tests"),
        "tools": copy_tree(HERE / "tools", target / "tools"),
    })
    return counts


def file_digest(path: Path) -> str:
    """Return a file digest for install verification."""
    return sha256(path.read_bytes()).hexdigest()


def tree_inventory(root: Path) -> dict[str, str]:
    """Return relative file digests for one managed tree."""
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)): file_digest(path)
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file())
    }


def copied_tree_errors(source: Path, target: Path) -> list[str]:
    """Report missing or changed managed files while allowing target extras."""
    errors = []
    for relative, expected in tree_inventory(source).items():
        installed = target / relative
        if not installed.is_file() or file_digest(installed) != expected:
            errors.append(f"installed file {installed} differs from the export")
    return errors


def installed_tree_errors(target: Path) -> list[str]:
    """Compare each copied tree and contract against the export."""
    errors = []
    for relative in (".agents/skills", ".claude/agents", "vendor/agent-sources",
                     "tests", "tools"):
        errors.extend(copied_tree_errors(HERE / relative, target / relative))
    if not (target / "AGENTS.md").is_file() or file_digest(target / "AGENTS.md") != file_digest(HERE / "AGENTS.md"):
        errors.append("installed AGENTS.md differs from the export")
    if not (target / "CLAUDE.md").is_file() or file_digest(target / "CLAUDE.md") != file_digest(HERE / "CLAUDE.md"):
        errors.append("installed CLAUDE.md differs from the export")
    return errors


def installed_hook_errors(target: Path) -> list[str]:
    """Compare installed hook files and config against the export."""
    errors = []
    config = target / ".codex/hooks.json"
    if not config.is_file() or config.read_bytes() != render_hooks_config(target):
        errors.append("installed .codex/hooks.json differs from the rendered export")
    for name in CODEX_HOOK_MODULES:
        installed = target / ".codex/hooks" / name
        source = HERE / "tools/harness_templates/hooks" / name
        if not installed.is_file() or file_digest(installed) != file_digest(source):
            errors.append(f"installed hook {name} differs from the export")
    for name in OBSOLETE_CODEX_HOOKS:
        if (target / ".codex/hooks" / name).exists():
            errors.append(f"obsolete Codex hook remains: {name}")
    return errors


def installed_claude_hook_errors(target: Path) -> list[str]:
    """Compare Claude hooks and settings against the portable export."""
    errors = []
    settings = target / ".claude/settings.json"
    if not settings.is_file() or settings.read_bytes() != render_claude_settings(target):
        errors.append("installed .claude/settings.json differs from the rendered export")
    for name in CLAUDE_HOOK_MODULES:
        installed = target / ".claude/hooks" / name
        source = HERE / ".claude/hooks" / name
        if not installed.is_file() or file_digest(installed) != file_digest(source):
            errors.append(f"installed Claude hook {name} differs from the export")
    errors.extend(f"obsolete Claude hook remains: {name}" for name in OBSOLETE_CLAUDE_HOOKS
                  if (target / ".claude/hooks" / name).exists())
    return errors


def installed_claude_link_errors(target: Path) -> list[str]:
    """Check that Claude reads the canonical skill directories by symlink."""
    authority = target / ".agents/skills"
    links = target / ".claude/skills"
    names = sorted(entry.name for entry in authority.iterdir() if entry.is_dir())
    actual = sorted(entry.name for entry in links.iterdir()) if links.is_dir() else []
    errors = [] if actual == names else [f"installed Claude skill links are {actual!r}, expected {names!r}"]
    for name in names:
        link = links / name
        wanted = Path("../../.agents/skills") / name
        if not link.is_symlink() or link.readlink() != wanted:
            errors.append(f"installed Claude skill link differs from the export: {link}")
    return errors


def installed_ignore_errors(target: Path) -> list[str]:
    """Check that private method state remains outside Git."""
    errors = []
    ignore = target / ".gitignore"
    rules = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    for required in REQUIRED_IGNORES:
        if required not in rules:
            errors.append(f"installed .gitignore is missing {required}")
    return errors


def installed_memory_errors(target: Path) -> list[str]:
    """Require a usable private ledger while leaving its entries unmanaged."""
    path = target / "MEMORY.md"
    if not path.is_file():
        return [f"installed memory ledger is missing: {path}"]
    headings = set(path.read_text(encoding="utf-8").splitlines())
    required = {"## Ledger", "## Checkpoints"}
    missing = sorted(required - headings)
    return [f"installed memory ledger is missing headings: {missing!r}"] if missing else []


def install_errors(target: Path) -> list[str]:
    """Return every installed file that differs from the export bundle."""
    return [
        *installed_tree_errors(target),
        *installed_hook_errors(target),
        *installed_claude_hook_errors(target),
        *installed_claude_link_errors(target),
        *installed_ignore_errors(target),
        *installed_memory_errors(target),
    ]


def next_steps(target: Path) -> str:
    """Return the public checks for the installed method."""
    return (
        f"\nInstalled into {target}. Prove it:\n\n"
        f"    cd {target}\n"
        "    python3 tools/run_method_canaries.py --client codex\n"
        "    python3 tools/run_method_canaries.py --client claude\n"
        "    python3 -m unittest tests.test_shell_reading "
        "tests.test_agent_method_guard tests.test_claude_method_guard "
        "tests.test_claude_method_documents\n"
    )


def parse_arguments(arguments: list[str]) -> tuple[bool, Path]:
    """Parse install or check mode without accepting ambiguous arguments."""
    check = bool(arguments and arguments[0] == "--check")
    paths = arguments[1:] if check else arguments
    if len(paths) != 1:
        raise ValueError(f"usage: install.py [--check] <target-repository>, got {arguments!r}")
    return check, Path(paths[0]).resolve()


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Install the export or verify a previous install."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    check, target = parse_arguments(arguments)
    if check:
        errors = install_errors(target)
        if errors:
            stdout.write("INSTALL CHECK FAIL\n" + "\n".join(errors) + "\n")
            return 1
        stdout.write("INSTALL CHECK PASS\n")
        return 0
    counts = install(target)
    stdout.write("INSTALL PASS " + " ".join(
        f"{name}={count}" for name, count in sorted(counts.items())
    ))
    stdout.write(next_steps(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
