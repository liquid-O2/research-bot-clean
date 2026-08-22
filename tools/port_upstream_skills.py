#!/usr/bin/env python3
"""Copy Pocock + pstack workflow skills into the house tree.

Does not install trading-skill packs. Does not enable 20 competing
principle-* auto-invoke skills: those land under poteto-mode/references.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

HOUSE = Path("/workspace/.claude/skills")
POCOCK = Path("/tmp/skill-src/pocock/skills")
PSTACK = Path("/workspace/artifacts/cache/review/upstream_sources_20260821/allpstack")

HOUSE_BANNER = """
> **House port.** Tracker is `design/` markdown (no GitHub/Linear). Tests:
> `python3 -m unittest <module>` (pytest is not installed). One review pass,
> one fix pass (D-001). Read this file in full; do not skip to coding.
> After a `draft a plan` message, planning skills run first; implement
> skills run when YOU write `engine/` or `tools/` code.

"""


def _rewrite_frontmatter(text: str, name: str, description: str, when: str) -> str:
    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4 :].lstrip("\n")
    fm = (
        f"---\nname: {name}\ndescription: >\n  {description}\n"
        f"when-to-use: >\n  {when}\n---\n\n"
    )
    if HOUSE_BANNER.strip() not in body:
        body = HOUSE_BANNER.lstrip() + body
    return fm + body


def write_skill(name: str, src_text: str, description: str, when: str,
                extras: dict[str, Path] | None = None) -> None:
    dest = HOUSE / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "SKILL.md").write_text(
        _rewrite_frontmatter(src_text, name, description, when)
    )
    if extras:
        for rel, path in extras.items():
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)


def pstack_text(stem: str) -> str:
    return (PSTACK / f"{stem}_SKILL.md").read_text()


def main() -> int:
    # --- Pocock engineering / productivity ---
    write_skill(
        "grilling",
        (POCOCK / "productivity/grilling/SKILL.md").read_text(),
        "Grill the plan until every branch is resolved. Use when the user "
        "says draft a plan, write a plan, grill, or a decision is still foggy.",
        "draft a plan, write a plan, grill, ambiguous, decision tree",
    )
    write_skill(
        "to-spec",
        (POCOCK / "engineering/to-spec/SKILL.md").read_text(),
        "Turn the conversation into a written spec in design/. Use when the "
        "user says draft a plan, write a spec, to-spec, or after grilling.",
        "draft a plan, write a spec, to-spec, synthesize the spec",
    )
    write_skill(
        "to-tickets",
        (POCOCK / "engineering/to-tickets/SKILL.md").read_text(),
        "Break a spec or plan into tracer-bullet tickets with blocking edges. "
        "Use when the user says draft a plan, break this down, to-tickets, or "
        "the work is more than one slice.",
        "draft a plan, break this down, to-tickets, tracer bullet, slices",
    )
    write_skill(
        "wayfinder",
        (POCOCK / "engineering/wayfinder/SKILL.md").read_text(),
        "Chart a map of decision tickets when the work is bigger than one "
        "session. Use when the user says draft a plan for a large unknown, "
        "wayfind, fog of war, or the destination is known but the path is not.",
        "draft a plan, wayfind, too big, fog of war, destination",
    )
    extras_cd = {}
    cd = POCOCK / "engineering/codebase-design"
    for extra in ("DEEPENING.md", "DESIGN-IT-TWICE.md"):
        p = cd / extra
        if p.exists():
            extras_cd[extra] = p
    write_skill(
        "codebase-design",
        (cd / "SKILL.md").read_text(),
        "Deep modules: a lot of behaviour behind a small interface (Ousterhout). "
        "Use when designing a module, placing a seam, or making code testable "
        "or grep-able for agents.",
        "deep module, seam, interface, design this, module shape, Ousterhout",
        extras_cd,
    )
    extras_tdd = {}
    tdd = POCOCK / "engineering/tdd"
    for extra in ("tests.md", "mocking.md"):
        p = tdd / extra
        if p.exists():
            extras_tdd[f"references/{extra}"] = p
    write_skill(
        "tdd",
        (tdd / "SKILL.md").read_text(),
        "Red-green vertical slices. The user will not say implement — load "
        "this when YOU write engine/ or tools/ code, or when they say TDD "
        "or write tests. House: python3 -m unittest; one slice not a hundred tests.",
        "TDD, write tests, red-green, implement, first engine/ edit",
        extras_tdd,
    )
    write_skill(
        "diagnosing-bugs",
        (POCOCK / "engineering/diagnosing-bugs/SKILL.md").read_text(),
        "Hard-bug loop: build a tight red signal, minimise, hypothesise, "
        "instrument, fix. Use when something is broken, failing, stalling, "
        "or slow, before guessing.",
        "bug, broken, failing, stall, debug, diagnose, slow",
    )
    write_skill(
        "research",
        (POCOCK / "engineering/research/SKILL.md").read_text(),
        "Investigate a question against primary sources and write a cited "
        "note in the repo. Use when a fact is needed from docs, source, or APIs.",
        "research, look up, primary source, how does X work",
    )
    extras_proto = {}
    proto = POCOCK / "engineering/prototype"
    for extra in ("LOGIC.md", "UI.md"):
        p = proto / extra
        if p.exists():
            extras_proto[extra] = p
    write_skill(
        "prototype",
        (proto / "SKILL.md").read_text(),
        "Throwaway prototype to answer a design question. Use when a spike "
        "or sketch is cheaper than deciding on paper.",
        "prototype, spike, sketch, throwaway, does this feel right",
        extras_proto,
    )
    extras_wfa = {}
    wfa = POCOCK / "productivity/writing-for-agents"
    p = wfa / "SKILL-MECHANICS.md"
    if p.exists():
        extras_wfa["SKILL-MECHANICS.md"] = p
    write_skill(
        "writing-for-agents",
        (wfa / "SKILL.md").read_text(),
        "Write skills, AGENTS.md, and agent-facing docs. Use when creating "
        "or editing a skill or the routing table.",
        "write a skill, AGENTS.md, CLAUDE.md, pointer, description",
        extras_wfa,
    )

    # --- pstack workflows ---
    write_skill(
        "architect",
        pstack_text("architect"),
        "Sketch types and module shape before code, design it twice, scrap "
        "a wrong sketch. Use when drafting a plan that changes shape, or "
        "before implementing a new boundary.",
        "draft a plan, architect this, design this, sketch types, module boundary",
    )
    write_skill(
        "figure-it-out",
        pstack_text("figure-it-out"),
        "Design an auditable playbook when no narrower one fits. Use for a "
        "large migration, multi-part change, or work reviewed after you step away.",
        "figure it out, large migration, no playbook, ambitious, audit trail",
    )
    write_skill(
        "blast-radius",
        pstack_text("blast-radius"),
        "Prove the one fact a change is safe because of by running real code. "
        "Use before shipping a small scary diff, or what could this break.",
        "blast radius, what could this break, before merge, scary diff",
    )
    write_skill(
        "how",
        pstack_text("how"),
        "Build a traced model of what existing code does, before changing it.",
        "how does this work, ground the subsystem, traced model",
    )
    write_skill(
        "why",
        pstack_text("why"),
        "Recover why the code is shaped this way from primary sources, not vibes.",
        "why is this shaped, archaeology, provenance, rationale",
    )
    write_skill(
        "interrogate",
        pstack_text("interrogate"),
        "Adversarial multi-lens review of a design or diff before shipping.",
        "interrogate, contested design, adversarial review",
    )
    write_skill(
        "show-me-your-work",
        pstack_text("show-me-your-work"),
        "Decision trail for long autonomous work the human reviews later.",
        "show your work, decision trail, going to bed, autonomous run",
    )
    write_skill(
        "unslop",
        pstack_text("unslop"),
        "Cut AI tells from any writing. Apply to every user-visible sentence.",
        "unslop, writing, report, puffery, AI voice",
    )

    # poteto-mode + playbooks + principles as references (not auto-invoke)
    dest = HOUSE / "poteto-mode"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "SKILL.md").write_text(_rewrite_frontmatter(
        pstack_text("poteto-mode"),
        "poteto-mode",
        "Pstack development method: match a playbook, apply principles, "
        "verify on the real artifact. Use when drafting a plan or when YOU "
        "start implementing — copy the matching playbook steps verbatim first.",
        "draft a plan, implement, feature, bug fix, playbook, poteto, "
        "how we develop",
    ))
    pb = dest / "playbooks"
    pb.mkdir(exist_ok=True)
    for src in sorted(PSTACK.glob("poteto-mode_playbooks_*.md")):
        slug = src.name.replace("poteto-mode_playbooks_", "")
        shutil.copy2(src, pb / slug)
    pref = dest / "references" / "principles"
    pref.mkdir(parents=True, exist_ok=True)
    for src in sorted(PSTACK.glob("principle-*_SKILL.md")):
        slug = src.name.replace("_SKILL.md", "") + ".md"
        shutil.copy2(src, pref / slug)
    for src in PSTACK.glob("poteto-mode_references_*.md"):
        slug = src.name.replace("poteto-mode_references_", "")
        shutil.copy2(src, dest / "references" / slug)

    print("ported pocock+pstack workflows into", HOUSE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
