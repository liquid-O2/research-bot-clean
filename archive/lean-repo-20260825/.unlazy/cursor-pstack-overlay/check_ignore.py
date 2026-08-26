#!/usr/bin/env python3
"""G5: .cursorignore hides Claude, Codex, CLAUDE.md, and house routers."""
from pathlib import Path

REQUIRED = (
    ".claude/",
    ".codex/",
    "CLAUDE.md",
    ".agents/skills/plan-flow/",
    ".agents/skills/implement-flow/",
    ".agents/skills/unlazy/",
    ".agents/skills/ask-matt/",
)


def main() -> None:
    path = Path("/workspace/.cursorignore")
    if not path.is_file():
        raise SystemExit("missing .cursorignore")
    text = path.read_text()
    missing = [item for item in REQUIRED if item not in text]
    if missing:
        raise SystemExit(f"cursorignore missing {missing}")
    print("ignore_ok")


if __name__ == "__main__":
    main()
