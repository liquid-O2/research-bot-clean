#!/usr/bin/env python3
"""G3: project .cursor/skills is the override set, not a Pocock slash menu."""
from pathlib import Path

ROOT = Path("/workspace/.cursor/skills")
ALLOWED = {
    "poteto-mode",
    "principle-codebase-design",
    "writing-for-agents",
    "tdd",
    "unslop",
}
FORBIDDEN = {
    "grilling",
    "to-spec",
    "to-tickets",
    "wayfinder",
    "implement",
    "pocock-tdd",
    "code-review",
    "improve-codebase-architecture",
    "plan-flow",
    "implement-flow",
}


def main() -> None:
    names = {p.name for p in ROOT.iterdir()}
    extra = names - ALLOWED
    missing = ALLOWED - names
    present_forbidden = names & FORBIDDEN
    if extra or missing or present_forbidden:
        raise SystemExit(
            f"extra={sorted(extra)} missing={sorted(missing)} "
            f"forbidden={sorted(present_forbidden)}"
        )
    print("overlay_ok")


if __name__ == "__main__":
    main()
