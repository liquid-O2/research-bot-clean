#!/usr/bin/env python3
"""G4: Cursor rules and CURSOR.md exist without a 21-principle dump."""
from pathlib import Path

BANNED = (
    "MUST evaluate the complete principle catalog",
    "principle-laziness-protocol",
    "principle-foundational-thinking",
    "principle-redesign-from-first-principles",
)
REQUIRED_FILES = (
    Path("/workspace/CURSOR.md"),
    Path("/workspace/.cursor/rules/cursor-pstack.mdc"),
    Path("/workspace/.cursor/rules/smallest-change.mdc"),
    Path("/workspace/.cursor/rules/akita.mdc"),
)
NEEDED_PHRASES = {
    Path("/workspace/.cursor/rules/cursor-pstack.mdc"): (
        "/setup-pstack",
        "/poteto-mode",
        "poteto-agent",
        "alwaysApply: true",
    ),
    Path("/workspace/CURSOR.md"): (
        "/add-plugin pstack",
        "/setup-pstack",
        "/poteto-mode",
        ".cursor/skills",
    ),
    Path("/workspace/.cursor/rules/akita.mdc"): (
        "alwaysApply: true",
        "4-20 lines",
        "under 500 lines",
    ),
}


def main() -> None:
    for path in REQUIRED_FILES:
        if not path.is_file():
            raise SystemExit(f"missing {path}")
        text = path.read_text()
        for token in BANNED:
            if token in text:
                raise SystemExit(f"{path} catalog dump: {token}")
        for phrase in NEEDED_PHRASES.get(path, ()):
            if phrase not in text:
                raise SystemExit(f"{path} missing {phrase!r}")
    print("rules_ok")


if __name__ == "__main__":
    main()
