#!/usr/bin/env python3
"""Expose the canonical skills to Claude Code as symlinks, never as copies.

`.agents/skills` is the only skill authority in this repository (AGENTS.md).
Claude Code reads skills from `.claude/skills/<name>/SKILL.md` and follows a
symlink at `<name>`, so one link per skill gives Claude the identical bytes
Codex reads. Copying would create a second method to maintain, which is the
thing the single-authority rule exists to prevent.

Re-running converges: it refreshes every link, removes links for skills that no
longer exist, and refuses to delete anything that is not a symlink.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Sequence, TextIO

ROOT = Path(__file__).resolve().parent.parent
AUTHORITY = ROOT / ".agents/skills"
TARGET = ROOT / ".claude/skills"
RECEIPT = ROOT / ".codex/harness/install-receipt.json"
LINK_DEPTH_PREFIX = "../../.agents/skills"


def expected_names(receipt: Path) -> list[str]:
    """Return the skill names both clients must expose, from the install receipt."""
    value = json.loads(receipt.read_text(encoding="utf-8"))
    names = value.get("active_skill_names")
    if not isinstance(names, list) or not names:
        raise ValueError(f"install receipt has no active_skill_names: {receipt}")
    return sorted(str(name) for name in names)


def verify_authority(name: str, authority: Path) -> Path:
    """Return the canonical skill directory, or say exactly what is missing."""
    directory = authority / name
    if not (directory / "SKILL.md").is_file():
        raise ValueError(f"skill {name!r} has no SKILL.md under {authority}")
    return directory


def link_target(name: str) -> str:
    """Return the relative target, which resolves the same from either root.

    Both `.agents/skills/<name>` and `.claude/skills/<name>` sit three levels
    below the repository root, so the `../../../vendor/...` paths inside the
    router skills resolve identically whichever root the reader came from.
    """
    return f"{LINK_DEPTH_PREFIX}/{name}"


def write_link(name: str, target: Path) -> bool:
    """Create or refresh one skill link, reporting whether it changed."""
    link = target / name
    wanted = link_target(name)
    if link.is_symlink() and os.readlink(link) == wanted:
        return False
    remove_link(link)
    link.symlink_to(wanted)
    return True


def remove_link(link: Path) -> None:
    """Remove a symlink, refusing to touch a real file or directory."""
    if not link.exists() and not link.is_symlink():
        return
    if not link.is_symlink():
        raise ValueError(f"refusing to replace a real path with a link: {link}")
    link.unlink()


def stale_links(target: Path, names: Sequence[str]) -> list[Path]:
    """Return links for skills that are no longer active."""
    if not target.is_dir():
        return []
    wanted = set(names)
    return [entry for entry in sorted(target.iterdir())
            if entry.is_symlink() and entry.name not in wanted]


def install(names: Sequence[str], authority: Path, target: Path) -> tuple[int, int]:
    """Link every active skill and drop links for the rest."""
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        verify_authority(name, authority)
    changed = sum(write_link(name, target) for name in names)
    removed = stale_links(target, names)
    for link in removed:
        link.unlink()
    return changed, len(removed)


def verify(names: Sequence[str], target: Path) -> None:
    """Prove every link resolves to a readable SKILL.md before reporting success."""
    for name in names:
        resolved = (target / name).resolve()
        if not (resolved / "SKILL.md").is_file():
            raise ValueError(f"link for {name!r} does not resolve to a SKILL.md: {resolved}")


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Install the Claude skill links and print a receipt."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    receipt = Path(arguments[0]) if arguments else RECEIPT
    names = expected_names(receipt)
    changed, removed = install(names, AUTHORITY, TARGET)
    verify(names, TARGET)
    stdout.write(f"CLAUDE SKILLS PASS linked={len(names)} changed={changed} "
                 f"removed={removed} authority={AUTHORITY}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
