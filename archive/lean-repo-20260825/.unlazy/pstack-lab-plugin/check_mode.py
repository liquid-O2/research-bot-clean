#!/usr/bin/env python3
"""G2: poteto-mode indexes the folded pieces."""
from pathlib import Path

MODE = Path("/workspace/.cursor/plugins/pstack-lab/skills/poteto-mode/SKILL.md")
FEATURE = Path(
    "/workspace/.cursor/plugins/pstack-lab/skills/poteto-mode/playbooks/feature.md"
)
BUG = Path(
    "/workspace/.cursor/plugins/pstack-lab/skills/poteto-mode/playbooks/bug-fix.md"
)
PLAN = Path(
    "/workspace/.cursor/plugins/pstack-lab/skills/poteto-mode/references/plan.md"
)
NEEDED = {
    MODE: (
        "principle-codebase-design",
        "writing-for-agents",
        "references/one-pass.md",
        "references/grilling-flow.md",
        "references/tight-loop.md",
    ),
    FEATURE: ("two-axis-review.md", "one-pass.md", "seams.md"),
    BUG: ("tight-loop.md", "one-pass.md"),
    PLAN: ("wayfinder-planning.md", "grilling-flow.md"),
}


def main() -> None:
    for path, phrases in NEEDED.items():
        text = path.read_text()
        missing = [p for p in phrases if p not in text]
        if missing:
            raise SystemExit(f"{path} missing {missing}")
    print("mode_ok")


if __name__ == "__main__":
    main()
