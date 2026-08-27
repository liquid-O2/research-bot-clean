#!/usr/bin/env python3
"""Build Codex model_instructions_file: vendor Sol prompt plus follow-rules.md.

Codex model_instructions_file replaces the vendor system prompt.
Claude --append-system-prompt-file appends. follow-rules.md is the one-line
append only. This script is the Sol path.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/workspace")
VENDOR = ROOT / ".codex/sol-system-prompt.md"
FOLLOW = ROOT / ".codex/follow-rules.md"
OUT = ROOT / ".codex/sol-instructions.md"


def main() -> int:
    vendor = VENDOR.read_text(encoding="utf-8")
    follow = FOLLOW.read_text(encoding="utf-8").strip()
    lines = vendor.rstrip().splitlines()
    while lines and lines[-1].startswith("MUST:"):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    OUT.write_text("\n".join(lines) + "\n\n" + follow + "\n", encoding="utf-8")
    print(f"{OUT} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
