---
name: clean-code-for-agents
description: >
  Akita + Ousterhout + Uncle Bob ranked for agents (especially Codex).
  Use when writing or reviewing code, when Codex is the harness, after
  draft a plan when YOU start implementing, or when files are too large
  to grep. Standing law, not optional polish.
when-to-use: >
  draft a plan, implement, Codex, write code, refactor, grep, small files,
  unique names, clean code, Akita, Ousterhout, Uncle Bob, Karpathy
---

# Clean code for agents

The primary reader is the agent (Akita 2026). Uncle Bob and Ousterhout still hold; the ranking changed. Codex especially follows this file — it lives on AGENTS.md plus this skill.

## Ranked, most leverage first

1. **Small functions and small files.** One thing, well. Files under 500 lines (ideal 200–300). Functions 4–20 lines. A file you must page through gets misread.
2. **One responsibility per module** (Uncle Bob SRP). Tangled files force extra reads.
3. **Unique, searchable names.** A symbol should return <5 grep hits. Never `data`, `process`, `handler`, `Manager`. Grep is the agent's navigation API.
4. **Comments carry WHY and provenance**, not WHAT. Keep agent-written WHY comments. Delete `// increment i`. A constraint comment is a smell: encode it as a type, assert, or test, then delete the comment.
5. **Explicit types.** Python type hints on every public function. Types are the answer key.
6. **DRY.** Agents miss copies. Factor once.
7. **Tests the agent can run unattended.** One command: `python3 -m unittest <module>` or `bash tools/run_all_checks.sh`. F.I.R.S.T. One vertical slice, not a hundred tests.
8. **Predictable layout.** Follow existing engine/tools conventions; don't invent a new tree.
9. **Inject dependencies.** Don't hardcode vendors or hardware inside logic.
10. **Max ~2 nesting levels.** Early returns.
11. **Errors carry the offending value and the expected shape.**
12. **Formatter decides style.** Don't bikeshed.
13. **No obvious comments.** Token cost.

## Ousterhout (depth)

Deep module: lots of behaviour behind a small interface, at a clean seam, testable through that interface. If a test has to reach past the interface, the module is the wrong shape. Read `codebase-design` when placing a seam. Design it twice before locking the shape (`architect`, `designing-it-twice`).

## Karpathy (always-on)

Think before coding. Stop when confused — grep or probe, don't guess. Surgical diffs. If 200 lines could be 50, rewrite first. Every plan step is `1. [Step] → verify: [exact command]`.

## This repo

- pytest is not installed.
- Unique names are load-bearing for the C++/Python boundary.
- D- citations and WHY comments survive refactors.
- Unit tests are regression checks; the real-data slice is the evidence tier.

## Red flags

A 2000-line file · a generic name with 50 grep hits · `raise ValueError("invalid")` with no value · tests that mock our own modules · a refactor that adds layers without reducing reader load · writing all tests first then all code.
