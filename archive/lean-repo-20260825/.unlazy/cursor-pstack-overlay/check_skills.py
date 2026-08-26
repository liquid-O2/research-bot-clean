#!/usr/bin/env python3
"""G2: unique overlay skills present, house routers absent."""
from pathlib import Path

ROOT = Path("/workspace/.cursor/skills")
REQUIRED = (
    "codebase-design",
    "domain-modeling",
    "writing-for-agents",
    "grilling",
    "clean-code-for-agents",
    "implement",
    "pocock-tdd",
    "code-review",
    "improve-codebase-architecture",
    "to-spec",
    "to-tickets",
    "wayfinder",
    "diagnosing-bugs",
)
FORBIDDEN = ("plan-flow", "implement-flow", "unlazy", "ask-matt", "poteto-mode")
TARGET = Path("/workspace/.agents/skills")


def main() -> None:
    missing = [name for name in REQUIRED if not (ROOT / name / "SKILL.md").is_file()]
    present_forbidden = [name for name in FORBIDDEN if (ROOT / name).exists()]
    bad_links = []
    for name in REQUIRED:
        skill = ROOT / name
        if not skill.is_symlink():
            bad_links.append(f"{name}:not_symlink")
            continue
        dest = skill.resolve()
        if dest != (TARGET / name).resolve():
            bad_links.append(f"{name}->{dest}")
    if missing or present_forbidden or bad_links:
        raise SystemExit(
            f"missing={missing} forbidden={present_forbidden} bad_links={bad_links}"
        )
    print("overlay_ok")


if __name__ == "__main__":
    main()
