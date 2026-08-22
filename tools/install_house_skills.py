#!/usr/bin/env python3
"""Symlink the canonical skill tree into Codex, OpenCode, Grok, and user homes.

Canonical: /workspace/.claude/skills/<name>/
Does not copy bodies. Re-run after adding a skill.

  python3 tools/install_house_skills.py
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

CANON = Path("/workspace/.claude/skills")
GROK_ENTRY = Path("/workspace/.grok/skills/entry-v2-goal")
HOOK = Path("/workspace/.claude/hooks/optmem_continuity.py")
GROK_HOOKS = Path("/workspace/.grok/hooks/optmem.json")
CODEX_HOOKS = Path("/workspace/.codex/hooks.json")
HOME = Path.home()


def _link_dir(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        if dst.is_symlink() and dst.resolve() == src.resolve():
            return "ok"
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        elif dst.is_dir() and not any(dst.iterdir()):
            dst.rmdir()
        else:
            return f"skip exists {dst}"
    dst.symlink_to(src)
    return "linked"


def main() -> int:
    names = sorted(
        p.name for p in CANON.iterdir()
        if (p.is_dir() or p.is_symlink()) and (p / "SKILL.md").exists()
    )
    if not names:
        print("no skills in", CANON)
        return 1
    targets = [
        Path("/workspace/.agents/skills"),
        Path("/workspace/.codex/skills"),
        Path("/workspace/.opencode/skills"),
        HOME / ".codex/skills",
        HOME / ".config/opencode/skills",
        HOME / ".agents/skills",
    ]
    report = []
    for root in targets:
        root.mkdir(parents=True, exist_ok=True)
        for name in names:
            src = CANON / name
            st = _link_dir(src, root / name)
            report.append(f"{root}/{name}: {st}")
    grok_skills = Path("/workspace/.grok/skills")
    grok_skills.mkdir(parents=True, exist_ok=True)
    for name in names:
        if name == "entry-v2-goal":
            continue
        st = _link_dir(CANON / name, grok_skills / name)
        report.append(f"{grok_skills}/{name}: {st}")

    # User-level Grok hooks (always trusted).
    user_grok = HOME / ".grok/hooks"
    user_grok.mkdir(parents=True, exist_ok=True)
    dst = user_grok / "optmem.json"
    shutil.copy2(GROK_HOOKS, dst)
    report.append(f"copied {dst}")

    # User-level Codex hooks.
    HOME.joinpath(".codex").mkdir(parents=True, exist_ok=True)
    shutil.copy2(CODEX_HOOKS, HOME / ".codex/hooks.json")
    report.append(f"copied {HOME / '.codex/hooks.json'}")

    print(f"canonical skills: {len(names)}")
    print("\n".join(report))
    manifest = Path("/workspace/.claude/skills_install_receipt.json")
    manifest.write_text(json.dumps({
        "canonical": str(CANON),
        "names": names,
        "targets": [str(t) for t in targets],
    }, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
