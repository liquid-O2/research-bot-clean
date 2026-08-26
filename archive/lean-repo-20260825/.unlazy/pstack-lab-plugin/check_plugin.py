#!/usr/bin/env python3
"""G1: plugin manifest and required components exist."""
import json
from pathlib import Path

ROOT = Path("/workspace/.cursor/plugins/pstack-lab")
MANIFEST = ROOT / ".cursor-plugin" / "plugin.json"
REQUIRED_SKILLS = (
    "poteto-mode",
    "principle-codebase-design",
    "writing-for-agents",
    "tdd",
)
REQUIRED_REFS = (
    "skills/poteto-mode/references/one-pass.md",
    "skills/poteto-mode/references/grilling-flow.md",
    "skills/poteto-mode/references/tight-loop.md",
    "skills/poteto-mode/references/two-axis-review.md",
    "skills/poteto-mode/references/seams.md",
    "skills/poteto-mode/references/wayfinder-planning.md",
)


def main() -> None:
    data = json.loads(MANIFEST.read_text())
    if data.get("name") != "pstack-lab":
        raise SystemExit(f"bad name {data.get('name')}")
    for key in ("skills", "agents", "rules", "hooks"):
        if key not in data:
            raise SystemExit(f"manifest missing {key}")
    if not (ROOT / "agents" / "poteto-agent.md").is_file():
        raise SystemExit("missing poteto-agent")
    if not (ROOT / "hooks" / "nudge.py").is_file():
        raise SystemExit("missing nudge.py")
    for name in REQUIRED_SKILLS:
        if not (ROOT / "skills" / name / "SKILL.md").is_file():
            raise SystemExit(f"missing skill {name}")
    for rel in REQUIRED_REFS:
        if not (ROOT / rel).is_file():
            raise SystemExit(f"missing {rel}")
    print("plugin_ok")


if __name__ == "__main__":
    main()
